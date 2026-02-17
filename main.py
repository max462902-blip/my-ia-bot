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
def home(): return "Smart Link Bot is Running!"

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
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

# --- MAIN UPLOAD FUNCTION ---
async def process_and_upload(media, message_to_reply, original_msg=None):
    try:
        unique_id = uuid.uuid4().hex[:6] 
        
        if "video" in media.mime_type or (hasattr(media, "duration") and media.duration > 0):
            final_filename = f"video_{unique_id}.mp4"
            is_video = True
        else:
            final_filename = f"document_{unique_id}.pdf"
            is_video = False
        
        file_size = get_readable_size(media.file_size)

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
        
        if is_video:
            msg = f"✅ **Video Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("🎬 Play Video", url=branded_link)
        else:
            msg = f"✅ **PDF Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("📄 Open PDF", url=branded_link)

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
        await message.reply_text("✅ **Access Granted!**\nAb Topic/Forum wale links bhi kaam karenge.")
    else:
        await message.reply_text("🔒 **Bot Locked!**\nAccess ID bhejo. ( Telegram ID - @Kaal_shadow )")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 Bot Unlocked! Ab koi bhi link bhejo.")
        else:
            await message.reply_text("❌ Galat ID.")
        return

    # Link Handler
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot missing.")
        
        wait_msg = await message.reply_text("🕵️ **Fetching Link...**")
        try:
            # --- NEW SMART PARSING LOGIC ---
            # Pehle link ko saaf karo
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")

            # Logic Check
            if parts[0] == "c":
                # Private Link Format: c/CHAT_ID/MSG_ID or c/CHAT_ID/TOPIC_ID/MSG_ID
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1]) # Hamesha last wala message ID hota hai
            else:
                # Public Link Format: USERNAME/MSG_ID or USERNAME/TOPIC_ID/MSG_ID
                chat_id = parts[0] # Username
                msg_id = int(parts[-1]) # Hamesha last wala message ID hota hai
            
            # -------------------------------

            target_msg = await userbot.get_messages(chat_id, msg_id)
            media = target_msg.video or target_msg.document
            if not media:
                await wait_msg.delete()
                return await message.reply_text("❌ File nahi mili (Shayad text msg hai).")

            await wait_msg.delete()
            await process_and_upload(media, message, original_msg=target_msg)
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}\n\n*Note:* Agar private link hai to Userbot join hona chahiye.")

@bot.on_message(filters.video | filters.document)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Bot Locked, Access ID bhejo.")
    
    media = message.video or message.document
    await process_and_upload(media, message)

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
