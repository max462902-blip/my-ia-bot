import os
import uuid
import logging
import asyncio
import threading
from flask import Flask, redirect
from pyrogram import Client, filters
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Bot")

# --- FLASK SERVER (Render Keep-Alive) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Running High Speed!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    # Redirect to HuggingFace Direct Link
    return redirect(f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true", code=302)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)

# --- CONFIG ---
try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    HF_TOKEN = os.getenv("HF_TOKEN")
    HF_REPO = os.getenv("HF_REPO")
    SESSION_STRING = os.getenv("SESSION_STRING") # Private Link ke liye zaroori
except Exception as e:
    logger.error(f"Config Error: {e}")
    exit(1)

# --- CLIENTS (In-Memory: Purana session file use nahi karega) ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- QUEUE LOCK (Ek baar mein ek file) ---
upload_lock = asyncio.Lock()

# --- HELPER: RENAME & UPLOAD ---
async def process_media(media, message_to_reply, original_msg=None):
    # --- 1. ROBUST RENAMING LOGIC ---
    unique_id = uuid.uuid4().hex[:6]
    
    # Agar file ka naam hai to use karo, nahi to khud banao
    if hasattr(media, "file_name") and media.file_name:
        # Spaces hata kar underscore lagaya
        clean_name = media.file_name.replace(" ", "_")
        final_filename = f"{unique_id}_{clean_name}"
    else:
        # Agar naam nahi hai (Jaise Photo), to Extension detect karo
        if "Video" in str(type(media)): 
            final_filename = f"Video_{unique_id}.mp4"
        elif "Photo" in str(type(media)): 
            final_filename = f"Image_{unique_id}.jpg"
        elif "Audio" in str(type(media)): 
            final_filename = f"Audio_{unique_id}.mp3"
        else: 
            final_filename = f"File_{unique_id}.pdf"

    # Status Update
    status_msg = await message_to_reply.reply_text(f"⏳ **Processing...**\nFilename: `{final_filename}`")
    
    # Download Folder check
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = f"downloads/{final_filename}"

    try:
        # --- 2. DOWNLOAD ---
        await status_msg.edit("⬇️ **Downloading...**")
        
        if original_msg:
            # Userbot se download (Private Link)
            await original_msg.download(file_name=local_path)
        else:
            # Direct Bot se download (Forward/Upload)
            await message_to_reply.download(file_name=local_path)

        # --- 3. UPLOAD TO HUGGINGFACE ---
        await status_msg.edit("⬆️ **Uploading to Server...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # --- 4. CLEANUP & REPLY ---
        if os.path.exists(local_path): os.remove(local_path)

        final_link = f"{SITE_URL}/file/{final_filename}"
        
        await status_msg.delete()
        await message_to_reply.reply_text(
            f"✅ **Uploaded Successfully!**\n\n"
            f"📂 **Name:** `{final_filename}`\n"
            f"🔗 **Link:**\n`{final_link}`",
            disable_web_page_preview=True
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")
        # Error aane par bhi file delete karo taaki space na bhare
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLER 1: DIRECT FILES & FORWARDS ---
# (Photo bhi add kar diya hai)
@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_direct_file(client, message):
    # Queue System: Wait karega agar koi aur file upload ho rahi hai
    async with upload_lock:
        # Detect media type
        media = message.video or message.document or message.photo
        await process_media(media, message)

# --- HANDLER 2: LINKS (Private/Public) ---
@bot.on_message(filters.text & filters.private)
async def handle_links(client, message):
    text = message.text
    # Sirf Telegram links pakdega
    if "t.me/" not in text: return 

    if not userbot:
        return await message.reply_text("❌ Session String missing hai. Link work nahi karega.")

    async with upload_lock:
        wait_msg = await message.reply_text("🔎 **Checking Link via Userbot...**")
        try:
            # Link clean karo
            link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = link.split("/")
            
            # Logic: Chat ID aur Message ID nikaalo
            chat_id = None
            msg_id = None

            # Type 1: Private (/c/12345/67)
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1].split("?")[0]) 
            
            # Type 2: Public (username/67)
            else:
                chat_id = parts[0]
                msg_id = int(parts[-1].split("?")[0])

            # Message fetch karo
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if not target_msg or target_msg.empty:
                await wait_msg.edit("❌ Message nahi mila. Userbot join hona chahiye.")
                return

            # Media check
            media = target_msg.video or target_msg.document or target_msg.photo
            
            if not media:
                await wait_msg.edit("❌ Link mein koi File/Video/Photo nahi mili.")
                return

            await wait_msg.delete()
            # Ab process karo (Original msg userbot wala hai)
            await process_media(media, message, original_msg=target_msg)

        except Exception as e:
            await wait_msg.edit(f"❌ Error: `{e}`")

# --- START COMMAND ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Online!**\n\nAb aap bhej sakte hain:\n1. Direct Video/PDF/Photo\n2. Forwarded Files\n3. Private Channel Links")

# --- RUNNER ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("✅ Main Bot Starting...")
    await bot.start()
    
    if userbot:
        print("✅ Userbot Starting...")
        try:
            await userbot.start()
        except Exception as e:
            print(f"⚠️ Userbot Error: {e}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
