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

# --- DEBUG MODE ON ---
print("🚀 Starting bot...")
print(f"Python version: {os.sys.version}")
print(f"Current directory: {os.getcwd()}")

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:10000")

@app.route('/')
def home(): 
    return "Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"🔥 Flask starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- CONFIG ---
print("📥 Loading environment variables...")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_REPO = os.getenv("HF_REPO", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

print(f"✅ API_ID: {'✅' if API_ID else '❌'}")
print(f"✅ API_HASH: {'✅' if API_HASH else '❌'}")
print(f"✅ BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
print(f"✅ HF_TOKEN: {'✅' if HF_TOKEN else '❌'}")
print(f"✅ HF_REPO: {'✅' if HF_REPO else '❌'}")
print(f"✅ SESSION_STRING: {'✅' if SESSION_STRING else '❌'}")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- QUEUE & BATCH DATA ---
upload_queue = asyncio.Queue()
user_batches = {}
user_queue_numbers = {}

print("🤖 Creating bot client...")
# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

print(f"✅ Bot created: {bot}")
print(f"✅ Userbot created: {userbot}")

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    except:
        return "Unknown"

# --- WORKER PROCESSOR ---
async def worker_processor():
    print("👷 Worker processor started...")
    while True:
        try:
            print("👷 Waiting for queue...")
            task = await upload_queue.get()
            print(f"👷 Got task: {task}")
            
            client, message, media, media_type, original_msg, queue_msg = task
            user_id = message.chat.id
            
            local_path = None
            status_msg = None
            
            try:
                if queue_msg:
                    try: await queue_msg.delete()
                    except: pass

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

                unique_id = uuid.uuid4().hex[:6]
                ext = os.path.splitext(original_display_name)[1]
                if not ext: 
                    if media_type == "video": ext = ".mp4"
                    elif media_type == "photo": ext = ".jpg"
                    else: ext = ".pdf"
                
                final_filename = f"file_{unique_id}{ext}"

                status_msg = await message.reply_text(f"⏳ Processing: `{original_display_name}`")
                
                if not os.path.exists("downloads"): os.makedirs("downloads")
                local_path = f"downloads/{final_filename}"
                
                await status_msg.edit(f"⬇️ Downloading... `{original_display_name}`")
                
                print(f"📥 Downloading to: {local_path}")
                if original_msg:
                    await original_msg.download(file_name=local_path)
                else:
                    await message.download(file_name=local_path)
                
                print(f"✅ Downloaded: {local_path}")

                file_size = get_readable_size(os.path.getsize(local_path))

                await status_msg.edit(f"⬆️ Uploading... `{original_display_name}`")
                print(f"⬆️ Uploading to HF: {final_filename}")
                
                api = HfApi(token=HF_TOKEN)
                
                await asyncio.to_thread(
                    api.upload_file,
                    path_or_fileobj=local_path,
                    path_in_repo=final_filename,
                    repo_id=HF_REPO,
                    repo_type="dataset"
                )
                
                print(f"✅ Uploaded: {final_filename}")

                final_link = f"{SITE_URL}/file/{final_filename}"
                
                if user_id not in user_batches: 
                    user_batches[user_id] = []
                
                user_batches[user_id].append({
                    "display_name": original_display_name,
                    "link": final_link,
                    "size": file_size
                })

                await status_msg.delete()

            except Exception as e:
                print(f"❌ Processing error: {e}")
                if status_msg: 
                    await status_msg.edit(f"❌ Error: {str(e)}")
                logging.error(f"Error: {e}")
            
            finally:
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
                    print(f"🗑️ Deleted: {local_path}")
                upload_queue.task_done()

        except Exception as e:
            print(f"❌ Worker error: {e}")
            continue

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    print(f"📱 /start from user: {user_id}")
    print(f"Auth users: {AUTH_USERS}")
    
    if user_id in AUTH_USERS:
        await message.reply_text("✅ **Bot is Ready!**\nSend files or Telegram links.")
    else:
        await message.reply_text("🔒 **Locked!**\nSend password to unlock.")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    print(f"📝 Text from {user_id}: {text}")

    if user_id not in AUTH_USERS:
        if text == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Access Granted!**")
            print(f"✅ User {user_id} authenticated")
        else:
            await message.reply_text("❌ Wrong Password!")
        return

    if "t.me/" in text or "telegram.me/" in text:
        if not userbot:
            return await message.reply_text("❌ Userbot not configured!")
        
        try:
            print(f"🔗 Processing link: {text}")
            clean_link = text.replace("https://", "").replace("http://", "")
            clean_link = clean_link.replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            
            print(f"Link parts: {parts}")
            
            if "c" in parts:
                idx = parts.index("c")
                chat_id = int("-100" + parts[idx + 1])
                msg_id = int(parts[-1])
            else:
                chat_id = parts[0]
                msg_id = int(parts[-1].split("?")[0])
            
            print(f"Getting message from {chat_id}/{msg_id}")
            target_msg = await userbot.get_messages(chat_id, msg_id)
            print(f"Got message: {target_msg}")
            
            m_type = None
            if target_msg.document:
                m_type = "document"
            elif target_msg.video:
                m_type = "video"
            elif target_msg.photo:
                m_type = "photo"
            elif target_msg.audio:
                m_type = "audio"
            
            if m_type:
                media = getattr(target_msg, m_type)
                
                if user_id not in user_queue_numbers: 
                    user_queue_numbers[user_id] = 0
                user_queue_numbers[user_id] += 1
                q_pos = user_queue_numbers[user_id]
                
                queue_msg = await message.reply_text(f"🕒 **Added to Queue** (Position: {q_pos})")
                print(f"📤 Added to queue position {q_pos}")
                await upload_queue.put((client, message, media, m_type, target_msg, queue_msg))
            else:
                await message.reply_text("❌ No media found!")

        except Exception as e:
            print(f"❌ Link error: {e}")
            await message.reply_text(f"❌ Error: {str(e)}")

@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def handle_file(client, message):
    user_id = message.from_user.id
    
    if user_id not in AUTH_USERS:
        return
    
    print(f"📁 File from {user_id}")
    
    m_type = None
    if message.document:
        m_type = "document"
    elif message.video:
        m_type = "video"
    elif message.photo:
        m_type = "photo"
    elif message.audio:
        m_type = "audio"
    
    if not m_type:
        return
    
    media = getattr(message, m_type)

    if user_id not in user_queue_numbers: 
        user_queue_numbers[user_id] = 0
    user_queue_numbers[user_id] += 1
    q_pos = user_queue_numbers[user_id]

    queue_msg = await message.reply_text(f"🕒 **Added to Queue** (Position: {q_pos})")
    print(f"📤 Added file to queue position {q_pos}")
    
    await upload_queue.put((client, message, media, m_type, None, queue_msg))

async def main():
    print("🚀 Starting main()")
    try:
        print("🔥 Starting Flask thread...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("✅ Flask thread started")
        
        print("👷 Creating worker task...")
        asyncio.create_task(worker_processor())
        print("✅ Worker task created")
        
        print("🤖 Starting bot...")
        await bot.start()
        print("✅ Bot started successfully!")
        
        if userbot:
            print("🤖 Starting userbot...")
            await userbot.start()
            print("✅ Userbot started successfully!")
        
        print(f"🚀 Bot is running! Auth users: {AUTH_USERS}")
        print("📱 Send /start to your bot on Telegram")
        
        await idle()
        
    except Exception as e:
        print(f"❌ Main error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🛑 Stopping...")
        await bot.stop()
        if userbot:
            await userbot.stop()

if __name__ == "__main__":
    print("📝 Running main block")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
