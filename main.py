import os
import uuid
import threading
import logging
import asyncio
import time
import re
import random
from datetime import datetime
from flask import Flask, redirect
from pyrogram import Client, filters, idle, enums
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.WARNING)

# --- SERVER KEEPER (Render Health Check) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): 
    return "Bot is Running! Made by Kaal"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    if not hf_repo: return "HF_REPO not set", 404
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_REPO = os.environ.get("HF_REPO", "")
SESSION_STRING = os.environ.get("SESSION_STRING", None)
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "kp_2324")

AUTH_USERS = set()
upload_queue = asyncio.Queue()
user_batches = {}

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024
    return "Unknown"

# --- WORKER ---
async def worker_processor():
    print("👷 Worker started...")
    while True:
        task = await upload_queue.get()
        client, message, media, media_type, original_msg = task
        user_id = message.chat.id
        local_path = None
        status_msg = None
        try:
            file_name = getattr(media, "file_name", f"file_{int(time.time())}.{media_type}")
            unique_id = uuid.uuid4().hex[:6]
            ext = os.path.splitext(file_name)[1] or (".mp4" if media_type=="video" else ".jpg")
            final_filename = f"file_{unique_id}{ext}"

            status_msg = await message.reply_text(f"⏳ **Processing:** `{file_name}`")
            if not os.path.exists("downloads"): os.makedirs("downloads")
            local_path = f"downloads/{final_filename}"
            
            await status_msg.edit("⬇️ **Downloading...**")
            if original_msg: await original_msg.download(file_name=local_path)
            else: await message.download(file_name=local_path)

            file_size = get_readable_size(os.path.getsize(local_path))
            await status_msg.edit("⬆️ **Uploading to HF...**")
            
            api = HfApi(token=HF_TOKEN)
            await asyncio.to_thread(api.upload_file, path_or_fileobj=local_path, path_in_repo=final_filename, repo_id=HF_REPO, repo_type="dataset")

            final_link = f"{SITE_URL}/file/{final_filename}"
            if user_id not in user_batches: user_batches[user_id] = []
            user_batches[user_id].append({"name": file_name, "link": final_link, "size": file_size})
            await status_msg.delete()
        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {e}")
        finally:
            if local_path and os.path.exists(local_path): os.remove(local_path)
            upload_queue.task_done()
        
        if upload_queue.empty():
            await asyncio.sleep(2)
            if user_id in user_batches and user_batches[user_id]:
                res = "✅ **Batch Completed**\n\n"
                for item in user_batches[user_id]:
                    res += f"📂 {item['name']}\n🔗 `{item['link']}`\n📦 {item['size']}\n\n"
                await client.send_message(user_id, res)
                del user_batches[user_id]

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    # Har kisi ko reply dega jo /start karega
    await message.reply_text(f"👋 Hello {message.from_user.first_name}!\n🔒 Bot Locked hai. Password bhejo.")

@bot.on_message(filters.text & filters.private)
async def handle_txt(client, message):
    user_id = message.from_user.id
    # Agar user unlocked nahi hai
    if user_id not in AUTH_USERS:
        if message.text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Bot Unlocked!** Ab link ya file bhejo.")
        else:
            await message.reply_text("❌ Galat Password. Sahi dalo.")
        return

    # Agar link hai
    if "t.me/" in message.text:
        if not userbot: 
            return await message.reply_text("❌ Userbot (Session) nahi hai.")
        await message.reply_text("⏳ Processing Link...")
        # Link logic yahan short mein (original logic restored)
        try:
            clean = message.text.split('/')
            chat = int("-100" + clean[-2]) if clean[-3] == 'c' else clean[-2]
            msg_id = int(clean[-1])
            t_msg = await userbot.get_messages(chat, msg_id)
            m_type = "video" if t_msg.video else "photo" if t_msg.photo else "document"
            media = getattr(t_msg, m_type, None)
            if media:
                await upload_queue.put((client, message, media, m_type, t_msg))
        except Exception as e:
            await message.reply_text(f"Link Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_files(client, message):
    if message.from_user.id not in AUTH_USERS: 
        return await message.reply_text("🔒 Pehle password dalo.")
    m_type = "video" if message.video else "photo" if message.photo else "document"
    await upload_queue.put((client, message, getattr(message, m_type), m_type, None))

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    print("✅ System Online!")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
