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

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bot")

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")

# --- FLASK SERVER (LINK KE LIYE) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running! Send files."

@app.route('/file/<path:filename>')
def file_redirect(filename):
    # User ko Render ki link milegi, par background mein HF se download hoga
    real_url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- GLOBAL VARIABLES ---
# Queue ko global rakhenge par init main() me karenge
process_queue = None 
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER: CLEANUP ---
def clean_downloads():
    if os.path.exists("downloads"):
        shutil.rmtree("downloads")
    os.makedirs("downloads")

# --- HELPER: YOUTUBE DOWNLOADER ---
def download_youtube(url, output_folder):
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'{output_folder}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info.get('title', 'Video')
    except Exception as e:
        return None, str(e)

# --- WORKER (JO ASLI KAAM KAREGA) ---
async def worker():
    logger.info("👷 Worker Started...")
    while True:
        # Queue se task nikalo
        task = await process_queue.get()
        client, message, task_type, data = task
        
        status_msg = await message.reply_text("⏳ **Task added to queue...**")
        local_path = None
        
        try:
            # 1. DOWNLOADING
            clean_downloads() # Har baar folder saaf karo start me
            file_name = f"file_{uuid.uuid4().hex[:6]}"
            display_name = "Unknown"
            
            if task_type == "telegram_file":
                await status_msg.edit("⬇️ **Downloading from Telegram...**")
                file_name_ext = f"{file_name}.{data['ext']}"
                local_path = f"downloads/{file_name_ext}"
                
                # Telegram se download
                await client.download_media(
                    message=data['media'],
                    file_name=local_path
                )
                display_name = data['name']

            elif task_type == "youtube":
                await status_msg.edit("⬇️ **Downloading from YouTube...**")
                # YouTube se download (Thread me taki bot na ruke)
                local_path, name_or_err = await asyncio.to_thread(download_youtube, data['url'], "downloads")
                
                if not local_path:
                    raise Exception(f"YouTube Download Failed: {name_or_err}")
                
                display_name = name_or_err
                # Rename for safety
                ext = os.path.splitext(local_path)[1]
                new_path = f"downloads/{file_name}{ext}"
                os.rename(local_path, new_path)
                local_path = new_path
                file_name_ext = f"{file_name}{ext}"

            # 2. UPLOADING TO HUGGING FACE
            file_size = os.path.getsize(local_path) / (1024 * 1024) # MB me
            await status_msg.edit(f"⬆️ **Uploading to Server...**\nSize: {file_size:.2f} MB")
            
            api = HfApi(token=HF_TOKEN)
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=local_path,
                path_in_repo=file_name_ext,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            # 3. GENERATE LINK & DELETE FILE
            final_link = f"{SITE_URL}/file/{file_name_ext}"
            
            # Delete Local File (Important for 512MB RAM)
            if os.path.exists(local_path):
                os.remove(local_path)
            
            # Final Reply
            await status_msg.edit(
                f"✅ **Upload Complete!**\n\n"
                f"📂 **Name:** `{display_name}`\n"
                f"🔗 **Link:** {final_link}\n\n"
                f"⚠️ *File local storage se delete kar di gayi hai.*"
            )

        except Exception as e:
            logger.error(f"Error: {e}")
            await status_msg.edit(f"❌ Error: {str(e)}")
        
        finally:
            # Safai abhiyan
            clean_downloads()
            process_queue.task_done()

# --- HANDLERS ---

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def handle_files(client, message):
    # File details nikalo
    media = None
    name = "File"
    ext = "bin"

    if message.document:
        media = message.document
        name = message.document.file_name or "Document"
        ext = name.split(".")[-1] if "." in name else "bin"
    elif message.video:
        media = message.video
        name = "Video"
        ext = "mp4"
    elif message.audio:
        media = message.audio
        name = "Audio"
        ext = "mp3"
    elif message.photo:
        media = message.photo
        name = "Photo"
        ext = "jpg"

    # Queue me daalo
    await process_queue.put(
        (client, message, "telegram_file", {"media": media, "name": name, "ext": ext})
    )

@bot.on_message(filters.private & filters.text)
async def handle_links(client, message):
    text = message.text
    # Check for YouTube Links
    if "youtube.com" in text or "youtu.be" in text or "shorts" in text:
        await process_queue.put(
            (client, message, "youtube", {"url": text})
        )
    elif "/start" in text:
        await message.reply_text("👋 **Hi!**\nBhejo koi File, Video, ya YouTube link.\nMain usse Convert karke Direct Link dunga.")
    else:
        await message.reply_text("❌ Sirf Files ya YouTube Links bhejo.")

# --- MAIN EXECUTION ---
async def main():
    global process_queue
    
    # 1. Clean Trash
    clean_downloads()
    
    # 2. Initialize Queue inside the running loop (Fixes Loop Error)
    process_queue = asyncio.Queue()
    
    # 3. Start Flask in Thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 4. Start Worker
    asyncio.create_task(worker())
    
    # 5. Start Bot
    print("🤖 Bot Started!")
    await bot.start()
    await idle()
    await bot.stop()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(main())
