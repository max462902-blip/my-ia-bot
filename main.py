import os
import uuid
import threading
import logging
import asyncio
import glob
import sys

# --- SAFETY CHECK: LIBRARIES ---
try:
    from flask import Flask, redirect
    from pyrogram import Client, filters, idle
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from huggingface_hub import HfApi
    from dotenv import load_dotenv
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Library missing! {e}")
    print("Solution: requirements.txt mein wo library add karo.")
    sys.exit(1)

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SAFETY CHECK: ENVIRONMENT VARIABLES ---
print("🔍 Checking Variables...")
try:
    API_ID_RAW = os.getenv("API_ID")
    if not API_ID_RAW:
        raise ValueError("API_ID missing in Environment Variables")
    API_ID = int(API_ID_RAW.strip()) # Strip spaces automatically
    
    API_HASH = os.getenv("API_HASH")
    if not API_HASH:
        raise ValueError("API_HASH missing")
        
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing")
        
    print("✅ All Critical Variables Found!")
except Exception as e:
    print(f"❌ CONFIG ERROR: {e}")
    print("Render Dashboard > Environment mein jake check karo.")
    sys.exit(1)

HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- SESSION CLEANER ---
def clean_session_files():
    print("🧹 Cleaning old session files...")
    for session_file in glob.glob("*.session"):
        try:
            os.remove(session_file)
        except Exception as e:
            print(f"⚠️ Could not delete {session_file}: {e}")

clean_session_files()

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"⚠️ Flask Error: {e}")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
# Main Bot
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4, in_memory=True)

# Userbot (Conditional)
userbot = None
if SESSION_STRING:
    try:
        userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4, in_memory=True)
        print("✅ Userbot Client Initialized")
    except Exception as e:
        print(f"⚠️ Userbot Init Failed (Check String): {e}")
        userbot = None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- UPLOAD FUNCTION ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
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

        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{final_filename}"
        
        await status.edit("⬇️ **Downloading...**")
        
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        await status.edit("⬆️ **Uploading...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        branded_link = f"{SITE_URL}/file/{final_filename}"
        
        if media_type == "video":
            btn = InlineKeyboardButton("🎬 Play Video", url=branded_link)
        elif media_type == "photo":
            btn = InlineKeyboardButton("🖼️ View Image", url=branded_link)
        else:
            btn = InlineKeyboardButton("📄 Open PDF", url=branded_link)

        msg = f"✅ **{file_type_msg} Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"

        await status.delete()
        await message_to_reply.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))

    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")
    
    finally:
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ Access Granted!")
    else:
        await message.reply_text("🔒 Bot Locked! Send Password.")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 Unlocked!")
        else:
            await message.reply_text("❌ Wrong Password.")
        return

    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot inactive.")
        
        wait_msg = await message.reply_text("🕵️ Fetching...")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            if parts[0] == "c": chat_id = int("-100" + parts[1])
            else: chat_id = parts[0]
            msg_id = int(parts[-1].split("?")[0])

            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if target_msg.photo: m_type, media = "photo", target_msg.photo
            elif target_msg.video: m_type, media = "video", target_msg.video
            elif target_msg.document: m_type, media = "document", target_msg.document
            else: return await wait_msg.edit("❌ No media found.")

            await wait_msg.delete()
            await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS: return await message.reply_text("🔒 Locked!")
    
    if message.photo: m_type = "photo"
    elif message.video: m_type = "video"
    else: m_type = "document"

    if message.photo: media = message.photo
    elif message.video: media = message.video
    else: media = message.document

    await process_and_upload(media, message, media_type=m_type)

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🤖 Starting Bot Clients...")
    try:
        await bot.start()
        print("✅ Main Bot Online")
    except Exception as e:
        print(f"❌ Main Bot Start Error: {e}")
        return

    if userbot:
        try:
            await userbot.start()
            print("✅ Userbot Online")
        except Exception as e:
            print(f"⚠️ Userbot Start Error: {e}")

    await idle()
    await bot.stop()
    if userbot: 
        try: await userbot.stop()
        except: pass

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
