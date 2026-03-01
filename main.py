import os
import uuid
import logging
import asyncio
import threading
import time
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
from dotenv import load_dotenv
import yt_dlp

# --- SETUP ---
load_dotenv()
# Logging setup: Ye errors ko screen par dikhayega
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger("Bot")

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home(): return "Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    return redirect(f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true", code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

# --- CLIENTS ---
# Main Bot
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Userbot (Conditional)
userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- HELPER: UPLOAD ---
async def upload_process(local_path, filename, message, status_msg):
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
        await message.reply_text(
            f"✅ **Done!**\n\n📂 `{filename}`\n🔗 **Link:**\n`{final_link}`",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Upload Fail: {e}")
        await status_msg.edit(f"❌ Upload Error: {e}")
    finally:
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text("👋 **Bot Online!**\nSend files, YouTube links, or Private Channel links.")

# 1. YOUTUBE HANDLER
@bot.on_message(filters.regex(r"(youtube\.com|youtu\.be)"))
async def yt_handler(client, message):
    url = message.text
    status_msg = await message.reply_text("⬇️ **YouTube Download Started...**")
    
    unique_id = uuid.uuid4().hex[:6]
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/yt_{unique_id}.%(ext)s',
            'noplaylist': True,
            'quiet': True
        }
        
        # Run download in background thread
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = f"yt_{unique_id}.{info['ext']}"
            local_path = f"downloads/{filename}"
            
        await upload_process(local_path, filename, message, status_msg)
        
    except Exception as e:
        await status_msg.edit(f"❌ YT Error: {e}")

# 2. DIRECT MEDIA HANDLER
@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def media_handler(client, message):
    media = message.video or message.document or message.photo or message.audio
    
    # Simple Naming
    unique_id = uuid.uuid4().hex[:6]
    ext = ".file"
    if message.video: ext = ".mp4"
    elif message.photo: ext = ".jpg"
    elif message.audio: ext = ".mp3"
    elif message.document: ext = ".pdf"
    
    filename = f"file_{unique_id}{ext}"
    local_path = f"downloads/{filename}"
    if not os.path.exists("downloads"): os.makedirs("downloads")
    
    status_msg = await message.reply_text(f"⬇️ **Downloading...**")
    try:
        await message.download(file_name=local_path)
        await upload_process(local_path, filename, message, status_msg)
    except Exception as e:
        await status_msg.edit(f"Error: {e}")

# 3. TELEGRAM LINK HANDLER
@bot.on_message(filters.text & filters.private)
async def link_handler(client, message):
    text = message.text
    if "t.me/" not in text: return 

    if not userbot:
        return await message.reply_text("❌ Userbot (Session) is Not Connected.")

    wait_msg = await message.reply_text("🔎 **Searching via Userbot...**")
    try:
        link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
        parts = link.split("/")
        
        # Link Logic
        if parts[0] == "c":
            chat_id = int("-100" + parts[1])
            msg_id = int(parts[-1].split("?")[0])
        else:
            chat_id = parts[0]
            msg_id = int(parts[-1].split("?")[0])

        target = await userbot.get_messages(chat_id, msg_id)
        
        if not target.media:
            await wait_msg.edit("❌ No media found in that link.")
            return

        # Download via Userbot
        unique_id = uuid.uuid4().hex[:6]
        filename = f"ub_file_{unique_id}"
        local_path = f"downloads/{filename}"
        
        await wait_msg.edit("⬇️ **Downloading from Channel...**")
        path = await target.download() # Pyrogram auto-names it
        
        # Rename for upload
        final_name = os.path.basename(path)
        new_path = f"downloads/{final_name}"
        os.rename(path, new_path)
        
        await upload_process(new_path, final_name, message, wait_msg)

    except Exception as e:
        await wait_msg.edit(f"❌ Link Error: {e}")

# --- SAFE STARTUP ---
async def main():
    # 1. Start Flask
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("✅ Flask Server Started")

    # 2. Start Main Bot
    try:
        await bot.start()
        info = await bot.get_me()
        logger.info(f"✅ Main Bot Started: @{info.username}")
    except Exception as e:
        logger.error(f"❌ MAIN BOT FAIL: {e}")
        return

    # 3. Start Userbot (SAFE MODE)
    if userbot:
        try:
            logger.info("⏳ Connecting Userbot...")
            await userbot.start()
            logger.info("✅ Userbot Connected Successfully!")
        except Exception as e:
            logger.error(f"⚠️ Userbot FAILED to start: {e}")
            logger.error("⚠️ Bot will run WITHOUT Userbot features.")
            # Hum userbot variable ko None kar dete hain taaki aage crash na ho
            globals()['userbot'] = None
    
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    asyncio.run(main())
