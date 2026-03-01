import os
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
# Logging ko DEBUG level pe rakha hai taaki errors dikhein
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "All-Rounder Bot is Alive & Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- CONFIG ---
# Yahan galti hoti hai aksar, isliye error handling lagayi hai
try:
    API_ID = int(os.getenv("API_ID")) # Convert to INT
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    HF_TOKEN = os.getenv("HF_TOKEN")
    HF_REPO = os.getenv("HF_REPO")
    SESSION_STRING = os.getenv("SESSION_STRING")
except Exception as e:
    logger.error(f"❌ Config Error: {e}")
    exit(1)

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
# in_memory=True lagaya hai taaki purana session file use na ho
bot = Client(
    "main_bot_session", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    workers=4,
    in_memory=True 
)

userbot = Client(
    "user_bot_session", 
    api_id=API_ID, 
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
        import uuid
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
        
        status = await message_to_reply.reply_text(f"⏳ **Processing...**\n`{final_filename}`")

        # Download Path
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{final_filename}"
        
        await status.edit("⬇️ **Downloading...**")
        
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

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
        
        btn_text = "View File"
        if media_type == "video": btn_text = "🎬 Play Video"
        
        msg = f"✅ **{file_type_msg} Saved!**\n\n🔗 **Link:**\n`{branded_link}`"

        await status.delete()
        await message_to_reply.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=branded_link)]]))

    except Exception as e:
        logger.error(f"Upload Error: {e}")
        if status: await status.edit(f"❌ Error: {str(e)}")
        else: await message_to_reply.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        if local_path and os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    logger.info(f"Command Recieved from: {message.from_user.first_name}")
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ **Access Granted!**\nSend files now.")
    else:
        await message.reply_text(f"🔒 **Bot Locked!**\nSend Password to access.\nYour ID: `{message.from_user.id}`")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text
    
    logger.info(f"Text Message: {text} from {user_id}")

    # Access Check
    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Access Unlocked!** Ab files bhejo.")
        else:
            # FIX: Pehle ye silent tha, ab ye reply karega
            await message.reply_text("❌ **Wrong Password!** Sahi password bhejo.")
        return

    # Link Handler Logic
    if "t.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot nahi hai, link kaam nahi karega.")
        
        wait_msg = await message.reply_text("🔎 checking link...")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1].split("?")[0])
            else:
                chat_id = parts[0]
                msg_id = int(parts[-1].split("?")[0])
                
            target = await userbot.get_messages(chat_id, msg_id)
            
            if target.video: m_type, media = "video", target.video
            elif target.photo: m_type, media = "photo", target.photo
            elif target.document: m_type, media = "document", target.document
            else:
                await wait_msg.edit("❌ No media found.")
                return

            await wait_msg.delete()
            await process_and_upload(media, message, original_msg=target, media_type=m_type)
            
        except Exception as e:
            await wait_msg.edit(f"❌ Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Password bhejo pehle!")
    
    if message.photo: m_type = "photo"
    elif message.video: m_type = "video"
    else: m_type = "document"

    media = getattr(message, m_type)
    await process_and_upload(media, message, media_type=m_type)

# --- RUNNER ---
async def main():
    # Flask Thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("✅ Connecting to Telegram...")
    try:
        await bot.start()
        print(f"✅ Bot Started as @{(await bot.get_me()).username}")
    except Exception as e:
        print(f"❌ BOT START ERROR: {e}")
        return

    if userbot:
        try:
            await userbot.start()
            print("✅ Userbot Started")
        except Exception as e:
            print(f"⚠️ Userbot Error: {e}")

    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    asyncio.run(main())
