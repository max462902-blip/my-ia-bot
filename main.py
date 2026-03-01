import os
import uuid
import logging
import asyncio
import threading
import glob
from flask import Flask, redirect
from pyrogram import Client, filters
from huggingface_hub import HfApi
from dotenv import load_dotenv
import yt_dlp  # YouTube Downloader

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bot")

# --- FLASK SERVER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "All-Rounder Bot (YT + Telegram) Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    return redirect(f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true", code=302)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True) if SESSION_STRING else None

# --- QUEUE LOCK ---
upload_lock = asyncio.Lock()

# --- HELPER: UPLOAD TO HF ---
async def upload_to_hf(local_path, filename, message_obj, status_msg):
    try:
        await status_msg.edit(f"⬆️ **Uploading to Cloud...**\n`{filename}`")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )
        
        final_link = f"{SITE_URL}/file/{filename}"
        await status_msg.delete()
        await message_obj.reply_text(
            f"✅ **Uploaded!**\n\n📂 **File:** `{filename}`\n🔗 **Link:**\n`{final_link}`",
            disable_web_page_preview=True
        )
    except Exception as e:
        await status_msg.edit(f"❌ Upload Error: {e}")
    finally:
        if os.path.exists(local_path): os.remove(local_path)

# --- YOUTUBE DOWNLOADER ---
async def download_youtube_video(url, message):
    status_msg = await message.reply_text("⬇️ **Downloading from YouTube...**\n(Wait, this takes time)")
    unique_id = uuid.uuid4().hex[:6]
    
    # Options for yt-dlp
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # Best MP4 format
        'outtmpl': f'downloads/yt_{unique_id}.%(ext)s', # Save path
        'noplaylist': True,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename_ext = info['ext']
            final_filename = f"yt_{unique_id}.{filename_ext}"
            local_path = f"downloads/{final_filename}"
            
        await upload_to_hf(local_path, final_filename, message, status_msg)

    except Exception as e:
        await status_msg.edit(f"❌ YouTube Error: {e}")

# --- TELEGRAM DOWNLOADER ---
async def process_telegram_media(media, message, original_msg=None):
    unique_id = uuid.uuid4().hex[:6]
    
    # Naming Logic
    if hasattr(media, "file_name") and media.file_name:
        final_filename = f"{unique_id}_{media.file_name.replace(' ', '_')}"
    elif hasattr(media, "mime_type") and "image" in media.mime_type:
         final_filename = f"image_{unique_id}.jpg"
    elif hasattr(media, "mime_type") and "audio" in media.mime_type:
         final_filename = f"audio_{unique_id}.mp3"
    else:
        # Fallback based on type
        if "Video" in str(type(media)): final_filename = f"video_{unique_id}.mp4"
        elif "Photo" in str(type(media)): final_filename = f"image_{unique_id}.jpg"
        elif "Audio" in str(type(media)): final_filename = f"song_{unique_id}.mp3"
        else: final_filename = f"file_{unique_id}.pdf"

    status_msg = await message.reply_text(f"⏳ **Processing...**\n`{final_filename}`")
    local_path = f"downloads/{final_filename}"
    if not os.path.exists("downloads"): os.makedirs("downloads")

    try:
        await status_msg.edit("⬇️ **Downloading from Telegram...**")
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message.download(file_name=local_path)
            
        await upload_to_hf(local_path, final_filename, message, status_msg)

    except Exception as e:
        await status_msg.edit(f"❌ Download Error: {e}")
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready!**\nSupports:\n- YouTube Links\n- Telegram Links\n- Direct Video/PDF/Photo/MP3")

# 1. DIRECT FILE HANDLER (Video, PDF, Photo, Audio)
@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def handle_direct_file(client, message):
    async with upload_lock:
        media = message.video or message.document or message.photo or message.audio
        await process_telegram_media(media, message)

# 2. TEXT & LINK HANDLER
@bot.on_message(filters.text & filters.private)
async def handle_links(client, message):
    text = message.text

    # YOUTUBE CHECK
    if "youtube.com" in text or "youtu.be" in text:
        async with upload_lock:
            await download_youtube_video(text, message)
        return

    # TELEGRAM LINK CHECK
    if "t.me/" in text:
        if not userbot: return await message.reply_text("❌ Session String missing.")
        
        async with upload_lock:
            wait_msg = await message.reply_text("🔎 **Checking Telegram Link...**")
            try:
                link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
                parts = link.split("/")
                
                chat_id = int("-100" + parts[1]) if parts[0] == "c" else parts[0]
                msg_id = int(parts[-1].split("?")[0])

                target_msg = await userbot.get_messages(chat_id, msg_id)
                
                # Check all types
                media = target_msg.video or target_msg.document or target_msg.photo or target_msg.audio
                
                if not media:
                    await wait_msg.edit("❌ No Media found in link.")
                    return

                await wait_msg.delete()
                await process_telegram_media(media, message, original_msg=target_msg)
            
            except Exception as e:
                await wait_msg.edit(f"❌ Error: {e}")

# --- RUNNER ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    if userbot: await userbot.start()
    print("✅ Bot Started with YouTube Support!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
