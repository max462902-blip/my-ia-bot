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

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "All-Rounder Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- MAIN UPLOAD FUNCTION (Photo Added) ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
    try:
        unique_id = uuid.uuid4().hex[:6]
        
        # --- NAME & TYPE DETECTION ---
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
        
        # Reply Logic
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
            await message.reply_text("❌ Galat ID.")
        return

    # Link Handler
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot missing.")
        
        wait_msg = await message.reply_text("🕵️ **Fetching Content...**")
        try:
            # Smart Parsing
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")

            # Determine Chat ID
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
            else:
                chat_id = parts[0]
            
            # Determine Message ID (Last part is always msg_id)
            # Remove query parameters if any (like ?single)
            msg_id_part = parts[-1].split("?")[0]
            msg_id = int(msg_id_part)

            # Fetch Message
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            # Detect Media Type
            if target_msg.photo:
                media = target_msg.photo
                m_type = "photo"
            elif target_msg.video:
                media = target_msg.video
                m_type = "video"
            elif target_msg.document:
                media = target_msg.document
                m_type = "document"
            else:
                await wait_msg.delete()
                return await message.reply_text("❌ Is link par koi File/Photo nahi mili.")

            await wait_msg.delete()
            await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
            
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}\n\n*Note:* Agar private link hai to Userbot join hona chahiye.")

# DIRECT FILE HANDLER (Photo Added)
@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Locked!")
    
    if message.photo:
        media = message.photo
        m_type = "photo"
    elif message.video:
        media = message.video
        m_type = "video"
    else:
        media = message.document
        m_type = "document"

    await process_and_upload(media, message, media_type=m_type)

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    if userbot: await userbot.start()
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
