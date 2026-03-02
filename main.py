import os
import uuid
import logging
import asyncio
import threading
from flask import Flask, redirect
from pyrogram import Client, filters
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bot")

# --- FLASK SERVER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Renamer Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    # Seedha Download Link
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

userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- LOCK ---
upload_lock = asyncio.Lock()

# --- MAIN LOGIC ---
async def process_media(media, message_to_reply, original_msg=None):
    # 1. Generate Short Unique ID
    unique_id = uuid.uuid4().hex[:6] # e.g., e63f04

    # 2. STRICT RENAMING (Aapki Demand Ke Hisab Se)
    # Media type check karke wahi naam denge jo aapne manga hai
    
    media_type = str(type(media))
    
    if "Video" in media_type:
        final_filename = f"video_{unique_id}.mp4"
    elif "Photo" in media_type:
        final_filename = f"photo_{unique_id}.jpg"
    elif "Audio" in media_type:
        final_filename = f"music_{unique_id}.mp3"
    else:
        # Document ke liye: Agar PDF hai to pdf_, nahi to file_
        if hasattr(media, "mime_type") and "pdf" in media.mime_type:
            final_filename = f"pdf_{unique_id}.pdf"
        else:
            # Agar koi aur file hai (jaise zip/apk) to extension maintain karenge
            ext = getattr(media, "file_name", ".file").split('.')[-1]
            if len(ext) > 4: ext = "file" # Safety
            final_filename = f"file_{unique_id}.{ext}"

    status_msg = await message_to_reply.reply_text(f"⏳ **Processing...**\n`{final_filename}`")
    
    # Download Path
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = f"downloads/{final_filename}"

    try:
        # 3. DOWNLOAD
        await status_msg.edit("⬇️ **Downloading...**")
        
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # 4. UPLOAD
        await status_msg.edit("⬆️ **Uploading...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 5. CLEANUP & REPLY
        if os.path.exists(local_path): os.remove(local_path)

        final_link = f"{SITE_URL}/file/{final_filename}"
        
        await status_msg.delete()
        await message_to_reply.reply_text(
            f"✅ **Uploaded!**\n\n"
            f"📂 `{final_filename}`\n"
            f"🔗 **Link:**\n`{final_link}`",
            disable_web_page_preview=True
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---

# 1. Direct File / Forward Handler
@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def handle_direct_file(client, message):
    async with upload_lock:
        media = message.video or message.document or message.photo or message.audio
        await process_media(media, message)

# 2. Link Handler (Private/Public)
@bot.on_message(filters.text & filters.private)
async def handle_links(client, message):
    text = message.text
    if "t.me/" not in text: return 

    if not userbot:
        return await message.reply_text("❌ Userbot missing.")

    async with upload_lock:
        wait_msg = await message.reply_text("🔎 **Searching...**")
        try:
            link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = link.split("/")
            
            # Chat ID & Msg ID Parsing
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1].split("?")[0])
            else:
                chat_id = parts[0]
                msg_id = int(parts[-1].split("?")[0])

            target = await userbot.get_messages(chat_id, msg_id)
            
            media = target.video or target.document or target.photo or target.audio
            
            if not media:
                await wait_msg.edit("❌ No Media Found.")
                return

            await wait_msg.delete()
            await process_media(media, message, original_msg=target)

        except Exception as e:
            await wait_msg.edit(f"❌ Error: {e}")

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready!**\nSend Video, PDF, Photo, or Audio.")

# --- RUNNER ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    if userbot: await userbot.start()
    print("✅ Bot Started with Clean Rename Logic!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
