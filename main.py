import os
import uuid
import threading
import logging
import asyncio
import time
import re
import shutil
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
# Logging thoda badhaya hai taaki pata chale bot on hai ya nahi
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- SERVER KEEPER (Flask) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Running Successfully!"

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
ACCESS_PASSWORD = "kp_2424"  # Password Updated
AUTH_USERS = set()

# --- QUEUE & BATCH DATA ---
upload_queue = asyncio.Queue()
user_batches = {}
user_queue_numbers = {} 

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

# --- HELPER FUNCTIONS ---

def clean_trash():
    """Bot start hone par purana download data delete karega"""
    try:
        if os.path.exists("downloads"):
            shutil.rmtree("downloads")
            logger.info("🗑️ Old downloads folder deleted.")
        os.makedirs("downloads")
        logger.info("✅ New downloads folder created.")
    except Exception as e:
        logger.error(f"Error cleaning trash: {e}")

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- WORKER PROCESSOR ---
async def worker_processor():
    print("👷 Worker started and waiting for tasks...")
    while True:
        # Task nikalo
        task = await upload_queue.get()
        client, message, media, media_type, original_msg, queue_msg = task
        user_id = message.chat.id
        
        local_path = None
        status_msg = None
        
        try:
            # 1. PURANA "Added to Queue" DELETE KARO
            if queue_msg:
                try: await queue_msg.delete()
                except: pass

            # 2. EXACT ORIGINAL NAME LOGIC
            original_display_name = None
            
            if hasattr(media, "file_name") and media.file_name:
                original_display_name = media.file_name
            
            if not original_display_name:
                caption = message.caption or (original_msg.caption if original_msg else "")
                if caption:
                    clean_cap = re.sub(r'[\\/*?:"<>|]', "", caption.split('\n')[0])[:60]
                    ext = ".mp4" if media_type == "video" else ".pdf"
                    if media_type == "photo": ext = ".jpg"
                    original_display_name = f"{clean_cap}{ext}"
            
            if not original_display_name:
                original_display_name = f"File_{int(time.time())}.{media_type}"

            # 3. UNIQUE SYSTEM NAME
            unique_id = uuid.uuid4().hex[:6]
            ext = os.path.splitext(original_display_name)[1]
            if not ext: 
                if media_type == "video": ext = ".mp4"
                elif media_type == "photo": ext = ".jpg"
                else: ext = ".pdf"
            
            final_filename = f"file_{unique_id}{ext}"

            # 4. PROCESSING STATUS
            status_msg = await message.reply_text(f"⏳ **Processing:**\n`{original_display_name}`")
            
            # 5. DOWNLOAD
            local_path = f"downloads/{final_filename}"
            
            await status_msg.edit(f"⬇️ **Downloading...**\n`{original_display_name}`")
            
            if original_msg:
                await original_msg.download(file_name=local_path)
            else:
                await message.download(file_name=local_path)

            file_size = get_readable_size(os.path.getsize(local_path))

            # 6. UPLOAD
            await status_msg.edit(f"⬆️ **Uploading...**\n`{original_display_name}`")
            api = HfApi(token=HF_TOKEN)
            
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=local_path,
                path_in_repo=final_filename,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            # 7. SAVE DATA FOR LIST
            final_link = f"{SITE_URL}/file/{final_filename}"
            
            if user_id not in user_batches: user_batches[user_id] = []
            
            user_batches[user_id].append({
                "display_name": original_display_name,
                "link": final_link,
                "size": file_size
            })

            # 8. DELETE STATUS MSG
            await status_msg.delete()

        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {str(e)}")
            logging.error(f"Error in worker: {e}")
        
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            upload_queue.task_done()

        # --- FINAL LIST CHECK ---
        if upload_queue.empty():
            await asyncio.sleep(2)
            if upload_queue.empty() and user_id in user_batches and user_batches[user_id]:
                data = user_batches[user_id]
                
                final_text = f"✅ **BATCH COMPLETED ({len(data)} Files)**\n\n"
                
                for item in data:
                    final_text += f"📂 **{item['display_name']}**\n"
                    final_text += f"`{item['link']}`\n"
                    final_text += f"📦 {item['size']}\n\n"
                
                final_text += "⚡ **All files processed!**"
                
                try:
                    if len(final_text) > 4000:
                        parts = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                        for part in parts: await client.send_message(user_id, part)
                    else:
                        await client.send_message(user_id, final_text)
                except: pass
                
                # Cleanup Lists
                del user_batches[user_id]
                if user_id in user_queue_numbers: del user_queue_numbers[user_id]

# --- HANDLERS ---

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    if user_id in AUTH_USERS:
        await message.reply_text("✅ **Bot Ready Hai!**\nFiles ya Link bhejo.")
    else:
        await message.reply_text("🔒 **Bot Locked Hai!**\nAccess ke liye password bhejein.")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    # Password Logic
    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text(f"🔓 **Access Granted!**\nAb aap files bhej sakte hain.")
        else:
            await message.reply_text("❌ Galat Password.")
        return

    # Link Handler
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot set nahi hai.")
        
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            
            if parts[0] == "c": 
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[2].split("?")[0])
            else: 
                chat_id = parts[0]
                msg_id = int(parts[1].split("?")[0])
            
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            m_type = "document"
            if target_msg.photo: m_type = "photo"
            elif target_msg.video: m_type = "video"
            
            media = getattr(target_msg, m_type, None)
            
            if media:
                if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
                user_queue_numbers[user_id] += 1
                q_pos = user_queue_numbers[user_id]
                
                queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
                await upload_queue.put( (client, message, media, m_type, target_msg, queue_msg) )
            else:
                await message.reply_text("❌ Media nahi mila link par.")

        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

@bot.on_message((filters.video | filters.document | filters.photo) & filters.private)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS: 
        return await message.reply_text("🔒 Password bhejo pehle.")
    
    user_id = message.from_user.id
    m_type = "document"
    if message.photo: m_type = "photo"
    elif message.video: m_type = "video"
    
    media = getattr(message, m_type)

    if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
    user_queue_numbers[user_id] += 1
    q_pos = user_queue_numbers[user_id]

    queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
    
    await upload_queue.put( (client, message, media, m_type, None, queue_msg) )

async def main():
    # 1. Purana Data Saaf Karo
    clean_trash()
    
    # 2. Flask Server Start
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 3. Bots Start
    print("🤖 Bot Starting...")
    await bot.start()
    print("✅ Main Bot Started")
    
    if userbot: 
        await userbot.start()
        print("✅ Userbot Started")
    
    # 4. Worker Start
    asyncio.create_task(worker_processor())
    
    # 5. Keep Alive
    await idle()
    
    # 6. Stop
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
