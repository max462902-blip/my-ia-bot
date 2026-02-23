import os
import time
import uuid
import shutil
import logging
import asyncio
import threading
import re
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from huggingface_hub import HfApi
import yt_dlp
from dotenv import load_dotenv

# --- SYSTEM SETUP ---
load_dotenv()
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("StealthBot")

# --- CONFIGURATION ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "") 
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_REPO = os.getenv("HF_REPO", "")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")
PASSWORD = os.environ.get("BOT_PASSWORD", "maharaja_jaswant_singh") 

# --- GLOBAL VARIABLES ---
auth_users = set()

# AUTO-BATCH VARIABLES (Jadu yahan hai)
user_queues = {}     # Files yahan jama hongi
user_timers = {}     # Timer yahan chalega

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home(): return "⚡ Server is Active."

@app.route('/file/<path:filename>')
def file_redirect(filename):
    real_url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- TELEGRAM SETUP ---
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_bot = None

# --- HELPER FUNCTIONS (UPDATED) ---

def get_secure_filename(original_name, media_type):
    # 1. Extension nikalo
    ext = ""
    if original_name and "." in original_name:
        ext = original_name.split(".")[-1].lower()
    
    # 2. Agar extension missing hai ya galat hai, to Force karo
    if media_type == "video" and ext not in ["mp4", "mkv", "mov"]:
        ext = "mp4"
    elif media_type == "audio" and ext not in ["mp3", "m4a", "wav"]:
        ext = "mp3"
    elif media_type == "photo" and ext not in ["jpg", "png", "jpeg"]:
        ext = "jpg"
    elif media_type == "document" and not ext:
        ext = "pdf" # Default for docs
    
    # 3. Random Name Generate karo
    random_id = uuid.uuid4().hex[:8]
    
    # 4. Prefix lagao taki file pehchani jaye
    prefix = media_type if media_type in ["video", "audio", "pdf"] else "file"
    
    return f"{prefix}_{random_id}.{ext}"

# --- PROCESSING ENGINE (UPDATED) ---

async def process_queue_engine(client, user_id):
    tasks = user_queues.get(user_id, [])
    if not tasks: return
    
    user_queues[user_id] = [] # Clear Queue
    total = len(tasks)
    completed_links = []
    
    # Batch Folder
    batch_id = uuid.uuid4().hex
    batch_folder = f"downloads/{batch_id}"
    os.makedirs(batch_folder, exist_ok=True)
    
    # Status Message
    status_msg = await client.send_message(
        user_id,
        f"⏳ **Batch Started...**\n"
        f"📊 Total Files: `{total}`"
    )
    
    try:
        for index, task in enumerate(tasks):
            current_num = index + 1
            data = task['data']
            task_type = task['type']
            
            # Variables Reset
            local_path = None
            final_path = None
            display_name = "Unknown_File"
            media_type = "document" # Default

            try:
                # --- STEP 1: DETECT TYPE & NAME ---
                
                if task_type in ["direct_media", "link"]:
                    msg = None
                    # ... (Message Fetching Logic Same) ...
                    if task_type == "direct_media":
                        msg = data['message_obj']
                    elif task_type == "link":
                        chat_id = data['chat_id']
                        msg_id = data['msg_id']
                        fetcher = user_bot if (data['is_private'] and user_bot) else client
                        try: msg = await fetcher.get_messages(chat_id, msg_id)
                        except: 
                            if user_bot: msg = await user_bot.get_messages(chat_id, msg_id)
                    
                    if not msg or not msg.media: raise Exception("Media Missing")
                    
                    # ✅ STRICT TYPE DETECTION
                    if msg.video:
                        media_type = "video"
                        display_name = msg.video.file_name or "Video.mp4"
                    elif msg.document:
                        media_type = "document"
                        display_name = msg.document.file_name or "Document.pdf"
                        # Agar document video hai (mkv/mp4)
                        if "video" in msg.document.mime_type: media_type = "video"
                    elif msg.audio:
                        media_type = "audio"
                        display_name = msg.audio.file_name or "Audio.mp3"
                    elif msg.photo:
                        media_type = "photo"
                        display_name = "Image.jpg"

                    # Update Status
                    await status_msg.edit(
                        f"⬇️ **Downloading ({current_num}/{total})**\n\n"
                        f"📂 File: `{display_name}`\n"
                        f"⚡ Please Wait..."
                    )

                    # ✅ DOWNLOAD WITH EXTENSION
                    downloader = user_bot if user_bot else client
                    # Hum pehle hi extension guess kar lenge
                    ext = display_name.split(".")[-1] if "." in display_name else "bin"
                    temp_filename = f"temp_{uuid.uuid4().hex}.{ext}"
                    
                    local_path = await downloader.download_media(msg, file_name=f"{batch_folder}/{temp_filename}")

                elif task_type == "youtube":
                    # ... (YouTube Logic) ...
                    local_path, yt_title = await asyncio.to_thread(download_youtube_secure, data['url'], batch_folder)
                    display_name = f"{yt_title}.mp4"
                    media_type = "video"

                # --- STEP 2: RENAME TO SECURE FORMAT ---
                if not local_path or not os.path.exists(local_path):
                    raise Exception("Download Failed")
                
                # Size Check
                file_size_bytes = os.path.getsize(local_path)
                file_size_mb = file_size_bytes / (1024 * 1024)

                # ✅ FORCE EXTENSION FIX
                secure_name = get_secure_filename(display_name, media_type)
                final_path = os.path.join(batch_folder, secure_name)
                
                # Rename/Move
                os.rename(local_path, final_path)

                # --- STEP 3: UPLOADING ---
                await status_msg.edit(
                    f"☁️ **Uploading ({current_num}/{total})**\n\n"
                    f"📂 File: `{display_name}`\n"
                    f"📦 Size: `{file_size_mb:.2f} MB`\n"
                    f"🚀 Sending to Cloud..."
                )

                api = HfApi(token=HF_TOKEN)
                await asyncio.to_thread(
                    api.upload_file,
                    path_or_fileobj=final_path,
                    path_in_repo=secure_name,
                    repo_id=HF_REPO,
                    repo_type="dataset"
                )

                final_link = f"{SITE_URL}/file/{secure_name}"
                
                # Entry Add
                entry = (
                    f"📂 **{display_name}**\n"
                    f"🔗 `{final_link}`\n"
                    f"📦 Size: {file_size_mb:.2f} MB"
                )
                completed_links.append(entry)

            except Exception as e:
                print(f"Error: {e}")
                completed_links.append(f"❌ **Error:** {display_name}\n⚠️ `{str(e)[:30]}`")

            finally:
                # ✅ DELETE LOCAL FILE IMMEDIATELY (Sequential cleanup)
                if final_path and os.path.exists(final_path): os.remove(final_path)
                if local_path and os.path.exists(local_path): os.remove(local_path)

    finally:
        if os.path.exists(batch_folder): shutil.rmtree(batch_folder)
        try: await status_msg.delete()
        except: pass

    # Final Message
    final_text = "**✅ Batch Processing Complete**\n\n" + "\n\n━━━━━━━━━━━━━━━━━━\n\n".join(completed_links)
    
    if len(final_text) > 4000:
        with open("Links.txt", "w", encoding="utf-8") as f:
            f.write(final_text.replace("**", "").replace("`", ""))
        await client.send_document(user_id, "Links.txt", caption="✅ **All Links Ready**")
        os.remove("Links.txt")
    else:
        await client.send_message(user_id, final_text, disable_web_page_preview=True)
# --- PROCESSING ENGINE (THE MAIN WORKER) ---

async def process_queue_engine(client, user_id):
    # Queue se tasks nikalo
    tasks = user_queues.get(user_id, [])
    if not tasks: return
    
    # Queue clear karo taki nayi files aa sakein
    user_queues[user_id] = []
    
    total = len(tasks)
    completed_links = []
    
    # 1. Batch Folder Create
    batch_id = uuid.uuid4().hex
    batch_folder = f"downloads/{batch_id}"
    os.makedirs(batch_folder, exist_ok=True)
    
    # First Task se message ka reference lo reply karne ke liye
    first_msg = tasks[0]['data'].get('message_obj') or tasks[0]['data'].get('original_msg')
    if not first_msg: return

    # 2. EK SINGLE STATUS MESSAGE
    status_msg = await client.send_message(
        user_id,
        f"⏳ **Batch Started...**\n"
        f"📊 Total Files: `{total}`"
    )
    
    try:
        for index, task in enumerate(tasks):
            current_num = index + 1
            data = task['data']
            task_type = task['type']
            
            # Variables Reset
            local_path = None
            final_path = None
            display_name = "Unknown File"
            file_size_mb = 0.0
            media_type = "document"

            try:
                # --- STEP 1: DOWNLOADING ---
                temp_name = data.get('name', 'File')
                
                # Update Status (Sirf Numbers Badlenge)
                await status_msg.edit(
                    f"⬇️ **Downloading ({current_num}/{total})**\n\n"
                    f"📄 File: `{temp_name}`\n"
                    f"⚡ Please Wait..."
                )

                if task_type in ["direct_media", "link"]:
                    msg = None
                    if task_type == "direct_media":
                        msg = data['message_obj']
                        display_name = data['name']
                    elif task_type == "link":
                        chat_id = data['chat_id']
                        msg_id = data['msg_id']
                        fetcher = user_bot if (data['is_private'] and user_bot) else client
                        try: msg = await fetcher.get_messages(chat_id, msg_id)
                        except: 
                            if user_bot: msg = await user_bot.get_messages(chat_id, msg_id)
                        
                        if not msg or not msg.media: raise Exception("Media Missing")
                        
                        if msg.document: 
                            display_name = msg.document.file_name or "Document"
                            media_type = "document"
                        elif msg.video: 
                            display_name = "Video File"
                            media_type = "video"
                        elif msg.audio: 
                            display_name = "Audio File"
                            media_type = "audio"
                        elif msg.photo: 
                            display_name = "Image"
                            media_type = "photo"

                    downloader = user_bot if user_bot else client
                    temp_filename = f"tg_{uuid.uuid4().hex}"
                    local_path = await downloader.download_media(msg, file_name=f"{batch_folder}/{temp_filename}")

                elif task_type == "youtube":
                    local_path, yt_title = await asyncio.to_thread(download_youtube_secure, data['url'], batch_folder)
                    if not local_path: raise Exception("YT Error")
                    display_name = yt_title
                    media_type = "video"

                # --- STEP 2: SIZE CHECK (Fix for 0.00 MB) ---
                if not local_path or not os.path.exists(local_path):
                    raise Exception("Download Failed")

                # ✅ Size Pehle check karo, move karne se pehle
                file_size_bytes = os.path.getsize(local_path)
                file_size_mb = file_size_bytes / (1024 * 1024)

                # --- STEP 3: RENAME ---
                secure_name = get_secure_filename(display_name if task_type != "youtube" else local_path, media_type)
                final_path = os.path.join(batch_folder, secure_name)
                os.rename(local_path, final_path)

                # --- STEP 4: UPLOADING ---
                await status_msg.edit(
                    f"☁️ **Uploading ({current_num}/{total})**\n\n"
                    f"📄 File: `{display_name}`\n"
                    f"📦 Size: `{file_size_mb:.2f} MB`\n"
                    f"🚀 Sending to Cloud..."
                )

                api = HfApi(token=HF_TOKEN)
                await asyncio.to_thread(
                    api.upload_file,
                    path_or_fileobj=final_path,
                    path_in_repo=secure_name,
                    repo_id=HF_REPO,
                    repo_type="dataset"
                )

                final_link = f"{SITE_URL}/file/{secure_name}"
                
                # ✅ FINAL LIST ENTRY
                entry = (
                    f"📂 **{display_name}**\n"
                    f"🔗 `{final_link}`\n"
                    f"📦 Size: {file_size_mb:.2f} MB"
                )
                completed_links.append(entry)

            except Exception as e:
                print(f"Error: {e}")
                completed_links.append(f"❌ **Error:** {display_name}\n⚠️ `{str(e)[:30]}`")

            finally:
                if final_path and os.path.exists(final_path): os.remove(final_path)
                if local_path and os.path.exists(local_path): os.remove(local_path)

    finally:
        if os.path.exists(batch_folder): shutil.rmtree(batch_folder)
        try: await status_msg.delete()
        except: pass

    # --- FINAL DELIVERY ---
    final_text = "**✅ Batch Processing Complete**\n\n" + "\n\n━━━━━━━━━━━━━━━━━━\n\n".join(completed_links)
    
    if len(final_text) > 4000:
        with open("Links.txt", "w", encoding="utf-8") as f:
            f.write(final_text.replace("**", "").replace("`", ""))
        await client.send_document(user_id, "Links.txt", caption="✅ **All Links Ready**")
        os.remove("Links.txt")
    else:
        await client.send_message(user_id, final_text, disable_web_page_preview=True)

# --- SMART HANDLER (AUTO BATCHING) ---

@bot.on_message(filters.private)
async def incoming_handler(client, message):
    # Ignore Commands
    if message.text and message.text.startswith("/"):
        if message.text.startswith("/start"):
             await auth_handler(client, message)
        return

    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""

    # 1. Auth Check
    if user_id not in auth_users:
        if text == PASSWORD:
            auth_users.add(user_id)
            await message.reply_text("✅ **Login Successful!**\nAb lagatar files bhejo, main khud batch bana lunga.")
        else:
            await message.reply_text("🔒 **Password Required.**")
        return

    # 2. Task Detection
    task = None
    if message.media:
        name = "File"
        if message.document: name = message.document.file_name or "Document"
        elif message.video: name = "Video File"
        task = {"type": "direct_media", "data": {"message_obj": message, "name": name, "original_msg": message}}

    elif text:
        if "youtube.com" in text or "youtu.be" in text:
            task = {"type": "youtube", "data": {"url": text}}
        elif "t.me/" in text:
            pvt_pattern = re.search(r"t\.me/c/(\d+)/(\d+)(?:/(\d+))?", text)
            pub_pattern = re.search(r"t\.me/([a-zA-Z0-9_]+)/(\d+)", text)
            if pvt_pattern:
                msg_id = int(pvt_pattern.group(3)) if pvt_pattern.group(3) else int(pvt_pattern.group(2))
                chat_id = int(f"-100{pvt_pattern.group(1)}")
                task = {"type": "link", "data": {"chat_id": chat_id, "msg_id": msg_id, "is_private": True}}
            elif pub_pattern:
                task = {"type": "link", "data": {"chat_id": pub_pattern.group(1), "msg_id": int(pub_pattern.group(2)), "is_private": False}}

    # 3. AUTO BATCHING LOGIC
    if task:
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Task add karo
        user_queues[user_id].append(task)
        
        # Agar pehle se timer chal raha hai to cancel karo (Kyunki nayi file aayi hai)
        if user_id in user_timers:
            user_timers[user_id].cancel()
        
        # Naya timer set karo (4 second ka wait)
        # Agar 4 second tak nayi file nahi aayi, to processing shuru
        user_timers[user_id] = asyncio.create_task(wait_and_process(client, user_id))
    else:
        if text != PASSWORD:
            await message.reply_text("❓ Unknown Format.")

async def wait_and_process(client, user_id):
    await asyncio.sleep(4) # 4 Second ka intezaar
    # Processing Shuru
    await process_queue_engine(client, user_id)
    if user_id in user_timers:
        del user_timers[user_id]

async def auth_handler(client, message):
    # Simple Start Message
    await message.reply_text("🔒 **Protected Bot**\nPassword bhejo chalu karne ke liye.")

# --- MAIN EXECUTION ---
async def main():
    global user_bot
    if not os.path.exists("downloads"): os.makedirs("downloads")
    
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Flask Server Started")

    if SESSION_STRING:
        try:
            user_bot = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
            await user_bot.start()
            print("✅ User Session Active")
        except: print("⚠️ User Session Invalid")

    print("🔥 Bot Ready to Auto-Batch!")
    await bot.start()
    await idle()
    await bot.stop()
    if user_bot: await user_bot.stop()

if __name__ == "__main__":
    try: loop = asyncio.get_event_loop()
    except RuntimeError: 
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
