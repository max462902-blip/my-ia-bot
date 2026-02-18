import os
import uuid
import threading
import logging
import asyncio
import time
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

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

# --- QUEUE & BATCH DATA ---
upload_queue = asyncio.Queue()
user_batches = {}

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

# --- WORKER PROCESSOR ---
async def worker_processor():
    print("👷 Worker started...")
    while True:
        # Queue se data nikalo
        # queue_msg wo message hai jo "Added to Queue" wala hai
        task = await upload_queue.get()
        client, message, media, media_type, original_msg, queue_msg = task
        user_id = message.chat.id
        
        local_path = None
        status_msg = None
        
        try:
            # 1. PURANA MESSAGE DELETE KARO (Added to Queue wala)
            try:
                if queue_msg: await queue_msg.delete()
            except:
                pass

            # 2. ORIGINAL NAME (Bilkul Same)
            original_display_name = "Unknown File"
            if media_type == "document":
                original_display_name = getattr(media, "file_name", "document.pdf")
            elif media_type == "video":
                original_display_name = getattr(media, "file_name", "video.mp4")
            elif media_type == "photo":
                original_display_name = "Image.jpg"
            
            # Agar naam khali ho to fallback
            if not original_display_name: original_display_name = "File"

            # 3. UNIQUE ID NAME (HF ke liye internal name)
            unique_id = uuid.uuid4().hex[:6]
            if media_type == "photo":
                final_filename = f"image_{unique_id}.jpg"
            elif media_type == "video":
                final_filename = f"video_{unique_id}.mp4"
            else:
                final_filename = f"document_{unique_id}.pdf"

            # 4. NEW STATUS MSG (Processing...)
            status_msg = await message.reply_text(f"⏳ **Processing:**\n`{original_display_name}`")
            
            # 5. DOWNLOAD
            if not os.path.exists("downloads"): os.makedirs("downloads")
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

            # 7. LINK DATA SAVE
            final_link = f"{SITE_URL}/file/{final_filename}"
            
            if user_id not in user_batches:
                user_batches[user_id] = []
            
            user_batches[user_id].append({
                "display_name": original_display_name, # Original Name List ke liye
                "link": final_link,
                "size": file_size
            })

            # 8. PROCESS COMPLETE - DELETE STATUS MSG
            await status_msg.delete()

        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {str(e)}")
            logging.error(f"Error: {e}")
        
        finally:
            # 9. STORAGE CLEANUP
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            
            upload_queue.task_done()

        # --- FINAL LIST GENERATOR ---
        if upload_queue.empty():
            await asyncio.sleep(2) # Thoda wait taaki confirm ho jaye
            
            if upload_queue.empty() and user_id in user_batches and user_batches[user_id]:
                data = user_batches[user_id]
                
                # Header
                final_text = f"✅ **BATCH COMPLETED ({len(data)} Files)**\n\n"
                
                for item in data:
                    # Name (Original)
                    # Link (One Tap Copy)
                    # Size
                    final_text += f"📂 **{item['display_name']}**\n"
                    final_text += f"`{item['link']}`\n"
                    final_text += f"📦 {item['size']}\n\n"
                
                final_text += "⚡ **All Done!**"
                
                try:
                    if len(final_text) > 4000:
                        parts = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                        for part in parts:
                            await client.send_message(user_id, part)
                    else:
                        await client.send_message(user_id, final_text)
                except:
                    pass
                
                del user_batches[user_id]

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ **Bot Ready!**\nSend multiple files, I will queue them.")
    else:
        await message.reply_text("🔒 **Locked!** Send Access Password.")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Unlocked!**")
        else:
            await message.reply_text("❌ Wrong Password.")
        return

    # Userbot Link Handler
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot Missing.")
        
        wait_msg = await message.reply_text("🕵️ **Checking Link...**")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            
            if parts[0] == "c": chat_id = int("-100" + parts[1])
            else: chat_id = parts[0]
            
            msg_id = int(parts[-1].split("?")[0])
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
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
                await wait_msg.edit("❌ No media found.")
                return

            await wait_msg.delete()
            
            # Queue Number Logic
            q_pos = upload_queue.qsize() + 1
            
            # Queue Msg Bhejo
            queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
            
            # Worker ko bhejo (queue_msg bhi pass kiya taaki wo delete kar sake)
            await upload_queue.put( (client, message, media, m_type, target_msg, queue_msg) )

        except Exception as e:
            await wait_msg.edit(f"❌ Error: {e}")

# Direct File Handler
@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Locked!")
    
    if message.photo: m_type = "photo"
    elif message.video: m_type = "video"
    else: m_type = "document"
    
    media = getattr(message, m_type)

    # Queue Number
    q_pos = upload_queue.qsize() + 1

    # Queue Msg Bhejo
    queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
    
    # Worker ko data + queue_msg bhejo
    await upload_queue.put( (client, message, media, m_type, None, queue_msg) )

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
