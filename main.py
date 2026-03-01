import os
import uuid
import threading
import logging
import asyncio
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER (Flask) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): 
    return "All-Rounder Bot is Running High Speed!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    if not hf_repo:
        return "Repo not set", 404
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    # Threading problem avoid karne ke liye debug=False
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- CONFIG CHECK ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# Check agar variables missing hain
if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("❌ API_ID, API_HASH ya BOT_TOKEN missing hai! .env check karo.")
    exit(1)

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
# Fix: in_memory=True lagaya hai taaki purana session file use na ho
bot = Client(
    "main_bot_session", 
    api_id=int(API_ID), 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=4,
    in_memory=True  # <--- YE ZAROORI HAI
)

# Userbot tabhi banega agar Session String ho
userbot = Client(
    "user_bot_session", 
    api_id=int(API_ID), 
    api_hash=API_HASH, 
    session_string=SESSION_STRING, 
    workers=4,
    in_memory=True
) if SESSION_STRING else None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- MAIN UPLOAD FUNCTION ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
    local_path = None
    status = None
    try:
        unique_id = uuid.uuid4().hex[:6]
        
        if media_type == "photo":
            final_filename = f"image_{unique_id}.jpg"
            file_type_msg = "🖼️ Image"
        elif media_type == "video":
            final_filename = f"video_{unique_id}.mp4"
            file_type_msg = "🎬 Video"
        else:
            final_filename = f"document_{unique_id}.pdf"
            file_type_msg = "📄 PDF"
        
        file_size = get_readable_size(getattr(media, "file_size", 0))

        status = await message_to_reply.reply_text(f"⏳ **Processing...**\n`{final_filename}`")

        # Download Path
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{final_filename}"
        
        await status.edit("⬇️ **Downloading...**")
        
        # Download
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # Upload
        await status.edit("⬆️ **Uploading to HF...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        branded_link = f"{SITE_URL}/file/{final_filename}"
        
        # Reply Logic
        btn_text = "Open File"
        if media_type == "video": btn_text = "🎬 Play Video"
        elif media_type == "photo": btn_text = "🖼️ View Image"
        
        btn = InlineKeyboardButton(btn_text, url=branded_link)
        msg = f"✅ **{file_type_msg} Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"

        await status.delete()
        await message_to_reply.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))

    except Exception as e:
        if status:
            await status.edit(f"❌ Error: {str(e)}")
        else:
            await message_to_reply.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup
        if local_path and os.path.exists(local_path): 
            os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    if user_id in AUTH_USERS:
        await message.reply_text("✅ **Access Granted!**\nAb PDF, Video aur **Photos** bhejo.")
    else:
        await message.reply_text("🔒 **Bot Locked!**\nAccess ID bhejo. ( Telegram ID - @Kaal_shadow )")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 Bot Unlocked! access id shi hai ab apni files bhej skte ho ")
        else:
            # Sirf tab reply karo agar password attempt ho, normal chat pe nahi
            # Taki user spam na feel kare
            pass 
        return

    # Link Handler
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: 
            return await message.reply_text("❌ Userbot (SESSION_STRING) missing hai.")
        
        wait_msg = await message.reply_text("🕵️ **Fetching Content...**")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")

            # Logic for Public vs Private links
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1].split("?")[0])
            else:
                chat_id = parts[0]
                msg_id = int(parts[-1].split("?")[0])

            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if target_msg.photo:
                media, m_type = target_msg.photo, "photo"
            elif target_msg.video:
                media, m_type = target_msg.video, "video"
            elif target_msg.document:
                media, m_type = target_msg.document, "document"
            else:
                await wait_msg.delete()
                return await message.reply_text("❌ Is link par supported File nahi mili.")

            await wait_msg.delete()
            await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
            
        except Exception as e:
            await wait_msg.edit(f"❌ Error: {e}\nCheck karo ki Userbot us channel/group mein joined hai.")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Pehle Access Password bhejo!")
    
    if message.photo:
        media, m_type = message.photo, "photo"
    elif message.video:
        media, m_type = message.video, "video"
    else:
        media, m_type = message.document, "document"

    await process_and_upload(media, message, media_type=m_type)

# --- STARTUP ---
async def main():
    # Flask ko alag thread mein run karo
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("✅ Bot Starting...")
    await bot.start()
    
    if userbot:
        print("✅ Userbot Starting...")
        try:
            await userbot.start()
        except Exception as ub_e:
            print(f"⚠️ Userbot Error: {ub_e} (Bot will run without Userbot)")
    
    # Bot info print karo confirm karne ke liye ki sahi bot chala hai
    me = await bot.get_me()
    print(f"🚀 Started as @{me.username}")
    
    await idle()
    
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    # Modern Asyncio Run
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Stopped.")
