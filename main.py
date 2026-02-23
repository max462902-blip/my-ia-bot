import os
import time
import uuid
import shutil
import logging
import asyncio
import threading
import re
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
import yt_dlp
from dotenv import load_dotenv

# --- SYSTEM SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO) # Changed to INFO for better debugging
logger = logging.getLogger("StealthBot")

# --- CONFIGURATION ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "") 
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_REPO = os.getenv("HF_REPO", "")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")
PASSWORD = os.environ.get("BOT_PASSWORD", "maharaja_jaswant_singh") # Better to use Env Var

# --- GLOBAL VARIABLES ---
auth_users = set()
user_batches = {} 
user_batch_mode = {}

# --- FLASK SERVER (Link Masking) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "⚡ Server is Active and Secure."

@app.route('/file/<path:filename>')
def file_redirect(filename):
    real_url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    # use_reloader=False is important for threading
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- TELEGRAM SETUP ---
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_bot = None
# We initialize user_bot later in main to handle async errors better

# --- HELPER FUNCTIONS ---

def get_secure_filename(original_name, media_type):
    random_id = uuid.uuid4().hex[:8]
    ext = "bin"
    if "." in original_name:
        ext = original_name.split(".")[-1].lower()

    if media_type == "video" or "mp4" in ext or "mkv" in ext:
        return f"video_{random_id}.mp4"
    elif media_type == "audio" or "mp3" in ext:
        return f"audio_{random_id}.mp3"
    elif media_type == "photo" or "jpg" in ext or "png" in ext:
        return f"image_{random_id}.jpg"
    elif media_type == "document" and "pdf" in ext:
        return f"pdf_{random_id}.pdf"
    else:
        return f"file_{random_id}.{ext}"

def download_youtube_secure(url, output_folder):
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{output_folder}/temp_%(id)s.%(ext)s',
            'noplaylist': True,
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'YouTube Video')
    except Exception as e:
        return None, str(e)

# --- PROCESSING ENGINE ---

async def process_queue_engine(client, message, tasks):
    total = len(tasks)
    completed_links = []
    
    # 1. BATCH FOLDER (Sab kuch isme download hoga)
    batch_id = uuid.uuid4().hex
    batch_folder = f"downloads/{batch_id}"
    os.makedirs(batch_folder, exist_ok=True)
    
    # 2. STATUS MESSAGE (Yehi bar-bar edit hoga)
    status_msg = await message.reply_text(
        f"⏳ **Initializing Batch...**\n"
        f"📊 Total Tasks: `{total}`"
    )
    
    try:
        for index, task in enumerate(tasks):
            current_num = index + 1
            data = task['data']
            task_type = task['type']
            
            # Variables Reset
            local_path = None
            final_path = None
            display_name = "Unknown File"
            file_size_mb = 0.0
            media_type = "document"

            try:
                # --- STEP 1: IDENTIFY NAME ---
                # User ko dikhane ke liye temporary naam
                temp_name_display = data.get('name', 'Video/File')
                
                # UPDATE STATUS: DOWNLOADING
                await status_msg.edit(
                    f"⬇️ **Downloading ({current_num}/{total})**\n\n"
                    f"📂 File: `{temp_name_display}`\n"
                    f"⚡ Please Wait..."
                )

                # --- STEP 2: DOWNLOAD LOGIC ---
                
                # A. TELEGRAM FILES
                if task_type in ["direct_media", "link"]:
                    msg = None
                    if task_type == "direct_media":
                        msg = data['message_obj']
                        display_name = data['name']
                    elif task_type == "link":
                        chat_id = data['chat_id']
                        msg_id = data['msg_id']
                        fetcher = user_bot if (data['is_private'] and user_bot) else client
                        try: msg = await fetcher.get_messages(chat_id, msg_id)
                        except: 
                            if user_bot: msg = await user_bot.get_messages(chat_id, msg_id)
                        
                        if not msg or not msg.media: raise Exception("Media not found.")
                        
                        # Type Detection
                        if msg.document: 
                            display_name = msg.document.file_name or "Document"
                            media_type = "document"
                        elif msg.video: 
                            display_name = "Video File"
                            media_type = "video"
                        elif msg.audio: 
                            display_name = "Audio File"
                            media_type = "audio"
                        elif msg.photo: 
                            display_name = "Image"
                            media_type = "photo"

                    downloader = user_bot if user_bot else client
                    temp_filename = f"tg_{uuid.uuid4().hex}"
                    local_path = await downloader.download_media(msg, file_name=f"{batch_folder}/{temp_filename}")

                # B. YOUTUBE VIDEO
                elif task_type == "youtube":
                    url = data['url']
                    ydl_opts = {
                        'format': 'best',
                        'outtmpl': f'{batch_folder}/yt_%(id)s.%(ext)s',
                        'noplaylist': True,
                        'quiet': True
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                        display_name = info.get('title', 'YouTube Video')
                        media_type = "video"
                        local_path = ydl.prepare_filename(info)

                # --- STEP 3: RENAME & SIZE FIX ---
                if not local_path or not os.path.exists(local_path):
                    raise Exception("Download Failed")

                # Cloud ke liye random naam generate karo
                secure_name = get_secure_filename(display_name if task_type != "youtube" else local_path, media_type)
                final_path = os.path.join(batch_folder, secure_name)
                
                # Rename/Move
                os.rename(local_path, final_path)

                # ✅ ACTUAL SIZE CALCULATION (Ab ye 100% sahi aayega)
                if os.path.exists(final_path):
                    file_size_bytes = os.path.getsize(final_path)
                    file_size_mb = file_size_bytes / (1024 * 1024)
                else:
                    file_size_mb = 0.0

                # --- STEP 4: UPLOADING ---
                # UPDATE STATUS: UPLOADING
                await status_msg.edit(
                    f"☁️ **Uploading ({current_num}/{total})**\n\n"
                    f"📂 File: `{display_name}`\n"
                    f"📦 Size: `{file_size_mb:.2f} MB`\n"
                    f"🚀 Sending to Cloud..."
                )

                api = HfApi(token=HF_TOKEN)
                await asyncio.to_thread(
                    api.upload_file,
                    path_or_fileobj=final_path,
                    path_in_repo=secure_name,
                    repo_id=HF_REPO,
                    repo_type="dataset"
                )

                final_link = f"{SITE_URL}/file/{secure_name}"
                
                # ✅ FINAL FORMAT (Link First, Size Last)
                entry = (
                    f"📂 **{display_name}**\n"
                    f"🔗 `{final_link}`\n"
                    f"📦 Size: {file_size_mb:.2f} MB"
                )
                completed_links.append(entry)

            except Exception as e:
                print(f"Error: {e}")
                completed_links.append(f"❌ **Error:** {display_name}\n⚠️ `{str(e)[:50]}`")

            finally:
                # Cleanup Individual File
                if final_path and os.path.exists(final_path): os.remove(final_path)
                if local_path and os.path.exists(local_path): os.remove(local_path)

    finally:
        # Cleanup Batch Folder
        if os.path.exists(batch_folder): shutil.rmtree(batch_folder)
        
        # Delete Status Message
        try: await status_msg.delete()
        except: pass

    # --- FINAL LIST SENDING ---
    final_text = "**✅ Batch Processing Complete**\n\n" + "\n\n━━━━━━━━━━━━━━━━━━\n\n".join(completed_links)
    
    if len(final_text) > 4000:
        with open("Direct_Links.txt", "w", encoding="utf-8") as f:
            f.write(final_text.replace("**", "").replace("`", ""))
        await message.reply_document("Direct_Links.txt", caption="✅ **All Links Ready**")
        os.remove("Direct_Links.txt")
    else:
        await message.reply_text(final_text, disable_web_page_preview=True)

# --- BOT COMMANDS & AUTHENTICATION ---

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    if user_id in auth_users:
        await message.reply_text("🔓 **Session Already Active.**\nLinks ya Files bhejo, main ready hoon.")
    else:
        await message.reply_text("🔒 **Protected System**\n\nAccess karne ke liye kripya **Password** likh kar bhejein.")

@bot.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    user_id = message.from_user.id
    if user_id not in auth_users:
        await message.reply_text("🚫 Pehle password bhej kar login karein.")
        return
        
    user_batch_mode[user_id] = True
    user_batches[user_id] = []
    await message.reply_text("📦 **Batch Mode Enabled.**\nFiles/Links bhejein. Jab ho jaye to `/process` dabayein.")

@bot.on_message(filters.command("process") & filters.private)
async def execute_batch(client, message):
    user_id = message.from_user.id
    if user_id not in auth_users:
        return

    tasks = user_batches.get(user_id, [])
    if not tasks:
        await message.reply_text("⚠️ **Queue Empty.**")
        return
    
    user_batch_mode[user_id] = False
    user_batches[user_id] = []
    asyncio.create_task(process_queue_engine(client, message, tasks))

@bot.on_message(filters.command("clear") & filters.private)
async def clear_queue(client, message):
    user_id = message.from_user.id
    if user_id in auth_users:
        user_batches[user_id] = []
        await message.reply_text("🗑 **Queue Cleared.**")

# --- SMART MESSAGE HANDLER (Password + Content) ---

@bot.on_message(filters.private)
async def smart_handler(client, message):
    # 1. Ignore other commands
    if message.text and message.text.startswith("/"):
        return 

    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # --- STEP 1: CHECK LOGIN ---
    if user_id not in auth_users:
        # Agar user logged in nahi hai, to check karo kya usne password bheja hai?
        if text == PASSWORD:
            auth_users.add(user_id)
            await message.reply_text("✅ **Access Granted!**\n\nAb aap Links ya Files bhej sakte hain.")
        else:
            await message.reply_text("❌ **Ghalat Password.**\nDobara koshish karein ya sahi password dalein.")
        return  # Yahi ruk jao, aage file process mat karo

    # --- STEP 2: PROCESS CONTENT (Agar User Logged In Hai) ---
    task = None
    
    # A. Detect Direct Files
    if message.media:
        name = "File"
        if message.document: name = message.document.file_name or "Document"
        elif message.video: name = "Video File"
        
        task = {
            "type": "direct_media",
            "data": {"message_obj": message, "name": name}
        }

    # B. Detect Text Links
    elif text:
        if "youtube.com" in text or "youtu.be" in text:
            task = {"type": "youtube", "data": {"url": text}}
        
        elif "t.me/" in text:
            # Telegram Link Patterns
            pvt_pattern = re.search(r"t\.me/c/(\d+)/(\d+)(?:/(\d+))?", text)
            pub_pattern = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", text)
            
            if pvt_pattern:
                msg_id = int(pvt_pattern.group(3)) if pvt_pattern.group(3) else int(pvt_pattern.group(2))
                chat_id = int(f"-100{pvt_pattern.group(1)}")
                task = {"type": "link", "data": {"chat_id": chat_id, "msg_id": msg_id, "is_private": True}}
            elif pub_pattern:
                task = {"type": "link", "data": {"chat_id": pub_pattern.group(1), "msg_id": int(pub_pattern.group(2)), "is_private": False}}

    # --- ACTION ---
    if task:
        if user_batch_mode.get(user_id):
            user_batches[user_id].append(task)
            await message.reply_text(f"➕ **Queued** (Total: {len(user_batches[user_id])})", quote=True)
        else:
            # Single Mode
            asyncio.create_task(process_queue_engine(client, message, [task]))
    else:
        # Agar na password tha, na link, na file
        if not user_batch_mode.get(user_id):
            await message.reply_text("❓ Kuch samajh nahi aaya. Link ya File bhejein.")

# --- MAIN EXECUTION ---
async def main():
    global user_bot
    
    # Ensure downloads folder exists
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # Start Flask in separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Flask Server Starting...")

    # Start User Bot (if configured)
    if SESSION_STRING:
        try:
            user_bot = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
            await user_bot.start()
            print("✅ User Session Started Successfully!")
        except Exception as e:
            print(f"⚠️ User Session Failed: {e}")
            user_bot = None

    # Start Main Bot
    print("🔥 Bot Started in Stealth Mode!")
    await bot.start()
    await idle()
    await bot.stop()
    if user_bot: await user_bot.stop()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
