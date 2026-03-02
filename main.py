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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bot")

# --- FLASK ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"

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

# --- CONSTANTS ---
MAX_FILE_SIZE = 500 * 1024 * 1024
ACCESS_PASSWORD = "Maharaja Jaswant Singh"
AUTH_USERS = set()

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Userbot Setup
userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

process_lock = asyncio.Lock()

# --- HELPER ---
async def process_media(media, message, original_msg=None):
    if getattr(media, "file_size", 0) > MAX_FILE_SIZE:
        return await message.reply_text("❌ File > 500MB")

    unique_id = uuid.uuid4().hex[:6]
    m_type = str(type(media))
    
    if "Video" in m_type: final_name = f"video_{unique_id}.mp4"
    elif "Photo" in m_type: final_name = f"photo_{unique_id}.jpg"
    elif "Audio" in m_type: final_name = f"music_{unique_id}.mp3"
    else: final_name = f"pdf_{unique_id}.pdf"

    status = await message.reply_text(f"⏳ **Processing...**\n`{final_name}`")
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = f"downloads/{final_name}"

    try:
        await status.edit("⬇️ **Downloading...**")
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message.download(file_name=local_path)

        await status.edit("☁️ **Uploading...**")
        api = HfApi(token=HF_TOKEN)
        await asyncio.to_thread(api.upload_file, path_or_fileobj=local_path, path_in_repo=final_name, repo_id=HF_REPO, repo_type="dataset")

        link = f"{os.environ.get('RENDER_EXTERNAL_URL')}/file/{final_name}"
        await status.delete()
        await message.reply_text(f"✅ **Done!**\n🔗 `{link}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Open", url=link)]]))

    except Exception as e:
        await status.edit(f"❌ Error: {e}")
    finally:
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS: await message.reply_text("✅ Ready")
    else: await message.reply_text("🔒 Password Required")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    if message.from_user.id not in AUTH_USERS:
        if message.text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(message.from_user.id)
            return await message.reply_text("🔓 Unlocked")
        return await message.reply_text("❌ Wrong Password")

    if "t.me/" in message.text:
        # --- DEBUG MODE ---
        if not userbot: return await message.reply_text("❌ Userbot Client Not Found")
        
        # Check connection explicitly
        if not userbot.is_connected:
            try:
                await userbot.start()
            except Exception as e:
                # YE ASLI ERROR DIKHAYEGA
                return await message.reply_text(f"❌ **Userbot Start Error:**\n`{str(e)}`")

        async with process_lock:
            wait = await message.reply_text("🔎 **Userbot Active! Searching...**")
            try:
                link = message.text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
                parts = link.split("/")
                
                if parts[0] == "c":
                    chat_id = int("-100" + parts[1])
                    msg_id = int(parts[-1].split("?")[0])
                else:
                    chat_id = parts[0]
                    msg_id = int(parts[-1].split("?")[0])

                target = await userbot.get_messages(chat_id, msg_id)
                
                if not target:
                    await wait.edit("❌ Message not found (Check permissions)")
                    return

                media = target.video or target.document or target.photo or target.audio
                if not media:
                    await wait.edit("❌ No Media")
                    return

                await wait.delete()
                await process_media(media, message, original_msg=target)
            except Exception as e:
                await wait.edit(f"❌ **Process Error:** `{str(e)}`")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_files(client, message):
    if message.from_user.id in AUTH_USERS:
        async with process_lock:
            media = message.video or message.document or message.photo
            await process_media(media, message)

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    # Hum userbot ko yahan start nahi karenge, demand par start karenge taaki error dikhe
    print("Bot Started")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
