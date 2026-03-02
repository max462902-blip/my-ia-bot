import os
import uuid
import logging
import asyncio
import threading
from flask import Flask, redirect
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("SecureBot")

# --- FLASK SERVER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "⚡ System Online ⚡"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    # Redirect user silently
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

# --- CONSTANTS ---
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB in Bytes
ACCESS_PASSWORD = "Maharaja Jaswant Singh"
AUTH_USERS = set()  # Jo log password daal chuke hain

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- LOCK (Storage Safety) ---
# Ek baar mein sirf ek upload taaki 512MB limit cross na ho
queue_lock = asyncio.Lock()

# --- HELPER FUNCTIONS ---
def get_size(size):
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return "Unknown"

async def safe_delete(path):
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"🗑️ Deleted: {path}")
    except:
        pass

# --- CORE LOGIC ---
async def process_media(media, message_to_reply, original_msg=None):
    # 1. CHECK SIZE (Crucial for Render)
    file_size = getattr(media, "file_size", 0)
    if file_size > MAX_FILE_SIZE:
        return await message_to_reply.reply_text(
            f"❌ **File Too Big!**\n\nLimit: 500MB\nYour File: {get_size(file_size)}\n\nProcess Cancelled to save server."
        )

    # 2. GENERATE FILENAME
    unique_id = uuid.uuid4().hex[:6]
    media_type = str(type(media))
    
    if "Video" in media_type:
        final_filename = f"video_{unique_id}.mp4"
        file_icon = "🎬"
    elif "Photo" in media_type:
        final_filename = f"photo_{unique_id}.jpg"
        file_icon = "🖼️"
    elif "Audio" in media_type:
        final_filename = f"music_{unique_id}.mp3"
        file_icon = "🎵"
    else:
        # PDF / Document
        if hasattr(media, "mime_type") and "pdf" in media.mime_type:
            final_filename = f"pdf_{unique_id}.pdf"
            file_icon = "📄"
        else:
            ext = getattr(media, "file_name", "file").split('.')[-1]
            if len(ext) > 4: ext = "file"
            final_filename = f"file_{unique_id}.{ext}"
            file_icon = "📂"

    # Status Message
    status = await message_to_reply.reply_text(f"⚙️ **Processing...**\n`{final_filename}`")
    
    # Path
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = f"downloads/{final_filename}"

    try:
        # 3. DOWNLOAD
        await status.edit("⬇️ **Downloading to Server...**")
        
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # 4. UPLOAD
        await status.edit("☁️ **Uploading to Cloud...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 5. GENERATE LINK
        final_link = f"{SITE_URL}/file/{final_filename}"
        
        # 6. PREMIUM UI REPLY
        await status.delete()
        
        btn = InlineKeyboardButton(f"{file_icon} Download / View", url=final_link)
        
        caption = (
            f"{file_icon} **File Uploaded Successfully!**\n\n"
            f"🆔 **ID:** `{final_filename}`\n"
            f"📦 **Size:** `{get_size(file_size)}`\n"
            f"🔗 **Link:**\n`{final_link}`"
        )
        
        await message_to_reply.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup([[btn]]),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await status.edit("❌ **Server Error!**\nProcess failed. File deleted.")
    
    finally:
        # 7. SAFETY DELETE (Chahe success ho ya fail, file udegi)
        await safe_delete(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("👋 **Welcome Back!**\nSend Video, PDF, Photo or Link.")
    else:
        await message.reply_text("🔒 **Access Denied!**\n\nEnter the **Password** to unlock me.")

@bot.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    text = message.text

    # --- PASSWORD CHECK ---
    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Access Granted!**\n\nAb aap Files ya Links bhej sakte hain.")
        else:
            await message.reply_text("❌ **Wrong Password!**\nTry again.")
        return

    # --- LINK HANDLING ---
    if "t.me/" in text:
        if not userbot: return await message.reply_text("⚠️ System Error: Userbot Missing.")
        
        async with queue_lock:
            wait_msg = await message.reply_text("🔍 **Analyzing Link...**")
            try:
                link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
                parts = link.split("/")
                
                if parts[0] == "c":
                    chat_id = int("-100" + parts[1])
                    msg_id = int(parts[-1].split("?")[0])
                else:
                    chat_id = parts[0]
                    msg_id = int(parts[-1].split("?")[0])

                target = await userbot.get_messages(chat_id, msg_id)
                media = target.video or target.document or target.photo or target.audio
                
                if not media:
                    await wait_msg.edit("⚠️ **No Media Found!**")
                    return

                await wait_msg.delete()
                await process_media(media, message, original_msg=target)

            except Exception as e:
                await wait_msg.edit("❌ **Link Error!**\nCheck if Userbot is joined in that channel.")

@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def file_handler(client, message):
    user_id = message.from_user.id
    
    # Auth Check
    if user_id not in AUTH_USERS:
        return await message.reply_text("🔒 **Locked!**\nEnter password first.")

    # Queue Check
    if queue_lock.locked():
        msg = await message.reply_text("⏳ **Queue Full!**\nWait for the current upload to finish...")
        
    async with queue_lock:
        if 'msg' in locals(): await msg.delete()
        media = message.video or message.document or message.photo or message.audio
        await process_media(media, message)

# --- RUNNER ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ System Started...")
    await bot.start()
    if userbot: 
        try: await userbot.start()
        except: pass
    await asyncio.Event().wait()

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
