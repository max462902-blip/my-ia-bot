import os
import uuid
import threading
import logging
import asyncio
import time
import re
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.WARNING)

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): 
    return "Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    if not hf_repo:
        return "HF_REPO not set", 404
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
# Try-Except lagaya hai taaki agar Variable missing ho toh bot crash na ho
try:
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
    HF_REPO = os.environ.get("HF_REPO", "")
    SESSION_STRING = os.environ.get("SESSION_STRING", None)
except Exception as e:
    print(f"Config Error: {e}")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- QUEUE & BATCH DATA ---
upload_queue = asyncio.Queue()
user_batches = {}
user_queue_numbers = {}

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4)

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- WORKER PROCESSOR ---
async def worker_processor():
    print("👷 Worker started...")
    while True:
        task = await upload_queue.get()
        client, message, media, media_type, original_msg, queue_msg = task
        user_id = message.chat.id
        
        local_path = None
        status_msg = None
        
        try:
            if queue_msg:
                try: await queue_msg.delete()
                except: pass

            original_display_name = getattr(media, "file_name", None)
            
            if not original_display_name:
                caption = message.caption or (original_msg.caption if original_msg else "")
                if caption:
                    clean_cap = re.sub(r'[\\/*?:"<>|]', "", caption.split('\n')[0])[:60]
                    ext = ".mp4" if media_type == "video" else ".jpg" if media_type == "photo" else ".pdf"
                    original_display_name = f"{clean_cap}{ext}"
            
            if not original_display_name:
                original_display_name = f"File_{int(time.time())}.{media_type}"

            unique_id = uuid.uuid4().hex[:6]
            ext = os.path.splitext(original_display_name)[1] or ".file"
            final_filename = f"file_{unique_id}{ext}"

            status_msg = await message.reply_text(f"⏳ **Processing:** `{original_display_name}`")
            
            if not os.path.exists("downloads"): os.makedirs("downloads")
            local_path = f"downloads/{final_filename}"
            
            await status_msg.edit(f"⬇️ **Downloading...**")
            
            if original_msg:
                await original_msg.download(file_name=local_path)
            else:
                await message.download(file_name=local_path)

            file_size = get_readable_size(os.path.getsize(local_path))

            await status_msg.edit(f"⬆️ **Uploading to HF...**")
            api = HfApi(token=HF_TOKEN)
            
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=local_path,
                path_in_repo=final_filename,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            final_link = f"{SITE_URL}/file/{final_filename}"
            
            if user_id not in user_batches: user_batches[user_id] = []
            user_batches[user_id].append({
                "display_name": original_display_name,
                "link": final_link,
                "size": file_size
            })

            await status_msg.delete()

        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {str(e)}")
        
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            upload_queue.task_done()

        if upload_queue.empty():
            await asyncio.sleep(2)
            if upload_queue.empty() and user_id in user_batches and user_batches[user_id]:
                data = user_batches[user_id]
                final_text = f"✅ **BATCH COMPLETED ({len(data)} Files)**\n\n"
                for item in data:
                    final_text += f"📂 **{item['display_name']}**\n`{item['link']}`\n📦 {item['size']}\n\n"
                
                try:
                    await client.send_message(user_id, final_text)
                except: pass
                del user_batches[user_id]
                if user_id in user_queue_numbers: del user_queue_numbers[user_id]

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ Ready! Bhejo files.")
    else:
        await message.reply_text("🔒 Bot Locked! Password bhejo.")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    if user_id not in AUTH_USERS:
        if message.text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 Unlocked!")
        else:
            await message.reply_text("❌ Wrong Password.")
        return

    if "t.me/" in message.text:
        if not userbot: return await message.reply_text("❌ Userbot Missing.")
        try:
            clean_link = message.text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            chat_id = int("-100" + parts[1]) if parts[0] == "c" else parts[0]
            msg_id = int(parts[-1].split("?")[0])
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            m_type = "video" if target_msg.video else "photo" if target_msg.photo else "document"
            media = getattr(target_msg, m_type, None)
            
            if media:
                if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
                user_queue_numbers[user_id] += 1
                queue_msg = await message.reply_text(f"🕒 Added to Queue ({user_queue_numbers[user_id]})", quote=True)
                await upload_queue.put((client, message, media, m_type, target_msg, queue_msg))
        except Exception as e:
            await message.reply_text(f"❌ Link Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS: return
    user_id = message.from_user.id
    m_type = "video" if message.video else "photo" if message.photo else "document"
    media = getattr(message, m_type)

    if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
    user_queue_numbers[user_id] += 1
    queue_msg = await message.reply_text(f"🕒 Added to Queue ({user_queue_numbers[user_id]})", quote=True)
    await upload_queue.put((client, message, media, m_type, None, queue_msg))

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
