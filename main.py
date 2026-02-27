import os
import uuid
import threading
import logging
import asyncio
import requests # Ye zaroori hai link generate karne ke liye
from flask import Flask, redirect, request
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER (Flask) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Online and Ready."

# --- VIEW LINK GENERATOR (Telegram Direct) ---
@app.route('/view/<file_id>')
def view_file(file_id):
    try:
        token = os.environ.get("BOT_TOKEN")
        # Telegram API se file path mangwana
        api_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
        resp = requests.get(api_url).json()
        
        if resp['ok']:
            file_path = resp['result']['file_path']
            # Direct Stream Link
            direct_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            return redirect(direct_url, code=302)
        else:
            return f"Error: {resp.get('description')} (File 20MB se badi ho sakti hai)", 404
            
    except Exception as e:
        return f"Server Error: {e}", 500

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")

ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
print("Connecting to Telegram...")
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- MAIN LOGIC ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
    status = None
    local_path = None
    try:
        print("Processing File...")
        status = await message_to_reply.reply_text("⏳ **Processing...**")
        
        unique_id = uuid.uuid4().hex[:6]
        original_name = getattr(media, "file_name", f"file_{unique_id}")
        
        if media_type == "video":
            final_filename = f"video_{unique_id}.mp4"
        else:
            ext = os.path.splitext(original_name)[1]
            if not ext: ext = ".pdf"
            final_filename = f"document_{unique_id}{ext}"

        file_size = get_readable_size(getattr(media, "file_size", 0))

        # 1. Download
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{final_filename}"
        
        await status.edit("⬇️ **Downloading...**")
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # 2. Upload to Chat
        await status.edit("⬆️ **Uploading to Chat...**")
        
        uploaded_msg = None
        if media_type == "video":
            uploaded_msg = await message_to_reply.reply_video(
                video=local_path,
                caption="⚙️ **Generating Link...**"
            )
        else:
            uploaded_msg = await message_to_reply.reply_document(
                document=local_path,
                caption="⚙️ **Generating Link...**"
            )

        # 3. Clean Local File
        if os.path.exists(local_path):
            os.remove(local_path)

        # 4. Generate Link
        file_id = None
        if uploaded_msg.video: file_id = uploaded_msg.video.file_id
        elif uploaded_msg.document: file_id = uploaded_msg.document.file_id
        
        if not file_id:
            await status.edit("❌ Error: File ID not found.")
            return

        view_link = f"{SITE_URL}/view/{file_id}"

        # 5. Caption Update
        if media_type == "document" or final_filename.endswith(".pdf"):
            final_caption = (
                f"**Chat Box PDF**\n\n"
                f"🏷️ **Name:** `{original_name}`\n"
                f"📦 **Size:** {file_size}\n\n"
                f"🔗 **One Tap Copy Link:**\n"
                f"`{view_link}`"
            )
            await uploaded_msg.edit_caption(final_caption)
            await status.delete()

        elif media_type == "video":
            video_caption = (
                f"🎬 **Video Uploaded**\n\n"
                f"🔗 **One Tap View Link:**\n"
                f"`{view_link}`"
            )
            await uploaded_msg.edit_caption(video_caption)
            await status.delete()

    except Exception as e:
        print(f"Error in process: {e}")
        if status: await status.edit(f"❌ Error: {e}")
        else: await message_to_reply.reply_text(f"❌ Error: {e}")
    
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    print(f"Command Recvd from {message.from_user.id}")
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ **Bot Ready!**")
    else:
        await message.reply_text("🔒 **Password Required.**")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text
    print(f"Text Recvd: {text}")

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Unlocked!** Send files now.")
        else:
            await message.reply_text("❌ Wrong Password.")
        return

    # Link Handling
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot missing.")
        
        status = await message.reply_text("🔎 **Checking...**")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            chat_id = int("-100" + parts[1]) if parts[0] == "c" else parts[0]
            msg_id = int(parts[-1].split("?")[0])

            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if target_msg.video:
                media = target_msg.video
                m_type = "video"
            elif target_msg.document:
                media = target_msg.document
                m_type = "document"
            else:
                await status.edit("❌ Only Video/PDF.")
                return

            await status.delete()
            await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
            
        except Exception as e:
            print(f"Link Error: {e}")
            await status.edit(f"❌ Error: {e}")

@bot.on_message(filters.document | filters.video)
async def handle_file(client, message):
    print(f"File Recvd from {message.from_user.id}")
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Locked.")
    
    m_type = "video" if message.video else "document"
    await process_and_upload(media=message.video or message.document, message_to_reply=message, media_type=m_type)

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot Starting...")
    await bot.start()
    if userbot: 
        print("Userbot Starting...")
        await userbot.start()
    print("ALL SYSTEMS ONLINE")
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
