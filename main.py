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
    
    # Create a unique folder for this batch to prevent collision
    batch_id = uuid.uuid4().hex
    batch_folder = f"downloads/{batch_id}"
    os.makedirs(batch_folder, exist_ok=True)
    
    status_msg = await message.reply_text(
        f"🔄 **Processing Batch...**\n"
        f"📁 Total Files: `{total}`\n"
        f"📡 Status: `Connecting to Cloud...`"
    )
    
    try:
        for index, task in enumerate(tasks):
            current_num = index + 1
            data = task['data']
            task_type = task['type']
            
            local_path = None
            display_name = "Unknown Content"
            media_type = "document"

            try:
                # --- 1. DOWNLOAD PHASE ---
                await status_msg.edit(
                    f"📥 **Task {current_num}/{total}**\n"
                    f"💾 Fetching: `{data.get('name', 'File')}`"
                )

                if task_type in ["direct_media", "link"]:
                    msg = None
                    if task_type == "direct_media":
                        msg = data['message_obj']
                        display_name = data['name']
                    elif task_type == "link":
                        chat_id = data['chat_id']
                        msg_id = data['msg_id']
                        fetcher = user_bot if (data['is_private'] and user_bot) else client
                        
                        try:
                            msg = await fetcher.get_messages(chat_id, msg_id)
                        except:
                            if user_bot: msg = await user_bot.get_messages(chat_id, msg_id)
                        
                        if not msg or not msg.media:
                            raise Exception("Media not found/accessible.")
                        
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

                    # Download to batch specific folder
                    downloader = user_bot if user_bot else client
                    temp_filename = f"temp_{uuid.uuid4().hex}"
                    local_path = await downloader.download_media(msg, file_name=f"{batch_folder}/{temp_filename}")

                elif task_type == "youtube":
                    local_path, yt_title = await asyncio.to_thread(download_youtube_secure, data['url'], batch_folder)
                    if not local_path: raise Exception("YT Download Error")
                    display_name = yt_title
                    media_type = "video"

                # --- 2. RENAME & UPLOAD PHASE ---
                if not local_path or not os.path.exists(local_path):
                    raise Exception("Download failed (File not found).")

                secure_name = get_secure_filename(display_name if task_type != "youtube" else local_path, media_type)
                # Keep file in batch folder, just rename
                final_path = os.path.join(batch_folder, secure_name)
                os.rename(local_path, final_path)

                file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
                
                await status_msg.edit(
                    f"📤 **Task {current_num}/{total}**\n"
                    f"☁️ Uploading: `{secure_name}`\n"
                    f"📦 Size: `{file_size_mb:.2f} MB`"
                )

                api = HfApi(token=HF_TOKEN)
                await asyncio.to_thread(
                    api.upload_file,
                    path_or_fileobj=final_path,
                    path_in_repo=secure_name,
                    repo_id=HF_REPO,
                    repo_type="dataset"
                )

                if os.path.exists(final_path):
                    os.remove(final_path)

                final_link = f"{SITE_URL}/file/{secure_name}"
                completed_links.append(f"📄 **{display_name}**\n`{final_link}`")

            except Exception as e:
                print(f"Error processing file: {e}")
                completed_links.append(f"❌ **Error:** {display_name}\n`{str(e)[:30]}`")

    finally:
        # --- CLEANUP BATCH FOLDER ---
        if os.path.exists(batch_folder):
            shutil.rmtree(batch_folder)

    # --- FINAL DELIVERY ---
    final_text = "✅ **Cloud Upload Complete**\n\n" + "\n\n".join(completed_links)
    
    if len(final_text) > 4000:
        with open("Direct_Links.txt", "w", encoding="utf-8") as f:
            f.write(final_text.replace("**", "").replace("`", ""))
        await message.reply_document("Direct_Links.txt", caption="✅ **Task Completed.** Links file mein hain.")
        os.remove("Direct_Links.txt")
    else:
        await message.reply_text(final_text)

# --- BOT COMMANDS ---

@bot.on_message(filters.command("start") & filters.private)
async def auth_handler(client, message):
    args = message.text.split(" ", 1)
    user_id = message.from_user.id
    
    if len(args) > 1 and args[1] == PASSWORD:
        auth_users.add(user_id)
        await message.reply_text("🔐 **Authorization Successful.**")
    elif user_id in auth_users:
        await message.reply_text("🔓 **Session Already Active.**")
    else:
        await message.reply_text("🚫 **ACCESS DENIED**")

@bot.on_message(filters.command("batch") & filters.user(list(auth_users)))
async def start_batch(client, message):
    user_id = message.from_user.id
    user_batch_mode[user_id] = True
    user_batches[user_id] = []
    await message.reply_text("📦 **Batch Mode Enabled.** Send files/links. Send `/process` when done.")

@bot.on_message(filters.command("process") & filters.user(list(auth_users)))
async def execute_batch(client, message):
    user_id = message.from_user.id
    tasks = user_batches.get(user_id, [])
    
    if not tasks:
        await message.reply_text("⚠️ **Queue Empty.**")
        return
    
    user_batch_mode[user_id] = False
    user_batches[user_id] = []
    
    asyncio.create_task(process_queue_engine(client, message, tasks))

@bot.on_message(filters.command("clear") & filters.user(list(auth_users)))
async def clear_queue(client, message):
    user_id = message.from_user.id
    user_batches[user_id] = []
    await message.reply_text("🗑 **Queue Cleared.**")

@bot.on_message(filters.private & filters.user(list(auth_users)))
async def content_handler(client, message):
    if message.text and message.text.startswith("/"): return 

    user_id = message.from_user.id
    task = None
    
    if message.media:
        name = "File"
        if message.document: name = message.document.file_name or "Document"
        elif message.video: name = "Video File"
        
        task = {
            "type": "direct_media",
            "data": {"message_obj": message, "name": name}
        }

    elif message.text:
        text = message.text
        if "youtube.com" in text or "youtu.be" in text:
            task = {"type": "youtube", "data": {"url": text}}
        
        elif "t.me/" in text:
            pvt_pattern = re.search(r"t\.me/c/(\d+)/(\d+)(?:/(\d+))?", text)
            pub_pattern = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", text)
            
            if pvt_pattern:
                msg_id = int(pvt_pattern.group(3)) if pvt_pattern.group(3) else int(pvt_pattern.group(2))
                chat_id = int(f"-100{pvt_pattern.group(1)}")
                task = {"type": "link", "data": {"chat_id": chat_id, "msg_id": msg_id, "is_private": True}}
            elif pub_pattern:
                task = {"type": "link", "data": {"chat_id": pub_pattern.group(1), "msg_id": int(pub_pattern.group(2)), "is_private": False}}

    if task:
        if user_batch_mode.get(user_id):
            user_batches[user_id].append(task)
            await message.reply_text(f"➕ **Queued** (Total: {len(user_batches[user_id])})", quote=True)
        else:
            asyncio.create_task(process_queue_engine(client, message, [task]))

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
