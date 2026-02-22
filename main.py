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
    return "âš¡ Server is Active and Secure."

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

async def worker_processor():
    print("👷 Worker started...")
    while True:
        # Task nikalo
        task = await upload_queue.get()
        client, message, media, media_type, original_msg, queue_msg = task
        user_id = message.chat.id
        
        local_path = None
        status_msg = None
        
        try:
            # 1. PURANA "Added to Queue" DELETE KARO
            if queue_msg:
                try: await queue_msg.delete()
                except: pass

            # 2. EXACT ORIGINAL NAME LOGIC (Improved)
            original_display_name = None
            
            # Pehle koshish: File ke attribute se naam nikalo
            if hasattr(media, "file_name") and media.file_name:
                original_display_name = media.file_name
            
            # Dusri koshish: Agar file name nahi hai, to Caption se banao
            if not original_display_name:
                caption = message.caption or (original_msg.caption if original_msg else "")
                if caption:
                    # Caption ki pehli line lo, max 50 words, aur safe banao
                    clean_cap = re.sub(r'[\\/*?:"<>|]', "", caption.split('\n')[0])[:60]
                    ext = ".mp4" if media_type == "video" else ".pdf"
                    if media_type == "photo": ext = ".jpg"
                    original_display_name = f"{clean_cap}{ext}"
            
            # Teesri koshish: Agar caption bhi nahi hai
            if not original_display_name:
                original_display_name = f"File_{int(time.time())}.{media_type}"

            # 3. UNIQUE SYSTEM NAME (HF Upload ke liye)
            unique_id = uuid.uuid4().hex[:6]
            ext = os.path.splitext(original_display_name)[1]
            if not ext: 
                if media_type == "video": ext = ".mp4"
                elif media_type == "photo": ext = ".jpg"
                else: ext = ".pdf"
            
            final_filename = f"file_{unique_id}{ext}"

            # 4. PROCESSING STATUS
            status_msg = await message.reply_text(f"⏳ **Processing:**\n`{original_display_name}`")
            
            # 5. DOWNLOAD
            if not os.path.exists("downloads"): os.makedirs("downloads")
            local_path = f"downloads/{final_filename}"
            
            await status_msg.edit(f"⬇️ **Downloading...**\n`{original_display_name}`")
            
            if original_msg:
                await original_msg.download(file_name=local_path)
            else:
                await message.download(file_name=local_path)

            file_size = get_readable_size(os.path.getsize(local_path))

            # 6. UPLOAD
            await status_msg.edit(f"⬆️ **Uploading...**\n`{original_display_name}`")
            api = HfApi(token=HF_TOKEN)
            
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=local_path,
                path_in_repo=final_filename,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            # 7. SAVE DATA FOR LIST
            final_link = f"{SITE_URL}/file/{final_filename}"
            
            if user_id not in user_batches: user_batches[user_id] = []
            
            user_batches[user_id].append({
                "display_name": original_display_name,
                "link": final_link,
                "size": file_size
            })

            # 8. DELETE STATUS MSG
            await status_msg.delete()

        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {str(e)}")
            logging.error(f"Error: {e}")
        
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            upload_queue.task_done()

        # --- FINAL LIST CHECK ---
        if upload_queue.empty():
            await asyncio.sleep(2)
            if upload_queue.empty() and user_id in user_batches and user_batches[user_id]:
                data = user_batches[user_id]
                
                final_text = f"✅ **BATCH COMPLETED ({len(data)} Files)**\n\n"
                
                for item in data:
                    final_text += f"📂 **{item['display_name']}**\n"
                    final_text += f"`{item['link']}`\n"
                    final_text += f"📦 {item['size']}\n\n"
                
                final_text += "⚡ **All files processed!**"
                
                try:
                    if len(final_text) > 4000:
                        parts = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                        for part in parts: await client.send_message(user_id, part)
                    else:
                        await client.send_message(user_id, final_text)
                except: pass
                
                # Cleanup Lists
                del user_batches[user_id]
                if user_id in user_queue_numbers: del user_queue_numbers[user_id]

# --- BOT COMMANDS & AUTHENTICATION ---

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    if user_id in auth_users:
        await message.reply_text("ðŸ”“ **Session Already Active.**\nLinks ya Files bhejo, main ready hoon.")
    else:
        await message.reply_text("ðŸ”’ **Protected System**\n\nAccess karne ke liye kripya **Password** likh kar bhejein.")

@bot.on_message(filters.command("batch") & filters.private)
async def start_batch(client, message):
    user_id = message.from_user.id
    if user_id not in auth_users:
        await message.reply_text("ðŸš« Pehle password bhej kar login karein.")
        return
        
    user_batch_mode[user_id] = True
    user_batches[user_id] = []
    await message.reply_text("ðŸ“¦ **Batch Mode Enabled.**\nFiles/Links bhejein. Jab ho jaye to `/process` dabayein.")

@bot.on_message(filters.command("process") & filters.private)
async def execute_batch(client, message):
    user_id = message.from_user.id
    if user_id not in auth_users:
        return

    tasks = user_batches.get(user_id, [])
    if not tasks:
        await message.reply_text("âš ï¸ **Queue Empty.**")
        return
    
    user_batch_mode[user_id] = False
    user_batches[user_id] = []
    asyncio.create_task(process_queue_engine(client, message, tasks))

@bot.on_message(filters.command("clear") & filters.private)
async def clear_queue(client, message):
    user_id = message.from_user.id
    if user_id in auth_users:
        user_batches[user_id] = []
        await message.reply_text("ðŸ—‘ **Queue Cleared.**")

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
            await message.reply_text("âœ… **Access Granted!**\n\nAb aap Links ya Files bhej sakte hain.")
        else:
            await message.reply_text("âŒ **Ghalat Password.**\nDobara koshish karein ya sahi password dalein.")
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
            await message.reply_text(f"âž• **Queued** (Total: {len(user_batches[user_id])})", quote=True)
        else:
            # Single Mode
            asyncio.create_task(process_queue_engine(client, message, [task]))
    else:
        # Agar na password tha, na link, na file
        if not user_batch_mode.get(user_id):
            await message.reply_text("â“ Kuch samajh nahi aaya. Link ya File bhejein.")

# --- MAIN EXECUTION ---
async def main():
    global user_bot
    
    # Ensure downloads folder exists
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # Start Flask in separate thread
    threading.Thread(target=run_flask, daemon=True).start()
    print("ðŸš€ Flask Server Starting...")

    # Start User Bot (if configured)
    if SESSION_STRING:
        try:
            user_bot = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
            await user_bot.start()
            print("âœ… User Session Started Successfully!")
        except Exception as e:
            print(f"âš ï¸ User Session Failed: {e}")
            user_bot = None

    # Start Main Bot
    print("ðŸ”¥ Bot Started in Stealth Mode!")
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
