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
def home(): return "All-Rounder Bot Running!"

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
SESSION_STRING = os.getenv("SESSION_STRING") # Userbot ke liye zaroori

# --- CLIENTS (In-Memory to avoid Session Conflicts) ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    print("✅ Userbot Client Configured")

# --- QUEUE LOCK ---
upload_lock = asyncio.Lock()

# --- HELPER: PROCESS & UPLOAD ---
async def process_media(media, message_to_reply, original_msg=None):
    # Determine Filename
    unique_id = uuid.uuid4().hex[:6]
    file_ext = ".pdf" # Default
    
    # Check Media Type
    if hasattr(media, "file_name") and media.file_name:
        # Try to keep original name but safe
        clean_name = media.file_name.replace(" ", "_")
        final_filename = f"{unique_id}_{clean_name}"
    else:
        # Fallback names
        if "Video" in str(type(media)): final_filename = f"video_{unique_id}.mp4"
        elif "Photo" in str(type(media)): final_filename = f"photo_{unique_id}.jpg"
        else: final_filename = f"file_{unique_id}.pdf"

    status_msg = await message_to_reply.reply_text(f"⏳ **Queue Locked... Processing**\n`{final_filename}`")
    local_path = f"downloads/{final_filename}"
    if not os.path.exists("downloads"): os.makedirs("downloads")

    try:
        # 1. Download
        await status_msg.edit("⬇️ **Downloading...**")
        
        if original_msg:
            # Userbot download
            await original_msg.download(file_name=local_path)
        else:
            # Direct bot download
            await message_to_reply.download(file_name=local_path)

        # 2. Upload to HuggingFace
        await status_msg.edit("⬆️ **Uploading to Cloud...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 3. Cleanup
        if os.path.exists(local_path): os.remove(local_path)

        # 4. Result
        final_link = f"{SITE_URL}/file/{final_filename}"
        await status_msg.delete()
        await message_to_reply.reply_text(
            f"✅ **Uploaded!**\n\n📂 `{final_filename}`\n🔗 **Link:**\n`{final_link}`",
            disable_web_page_preview=True
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")
        if os.path.exists(local_path): os.remove(local_path)

# --- DIRECT FILE HANDLER ---
@bot.on_message(filters.video | filters.document)
async def handle_direct_file(client, message):
    async with upload_lock:
        media = message.video or message.document
        await process_media(media, message)

# --- LINK HANDLER (Private/Public) ---
@bot.on_message(filters.text & filters.private)
async def handle_links(client, message):
    text = message.text
    if "t.me/" not in text:
        return # Ignore normal text

    if not userbot:
        return await message.reply_text("❌ Session String nahi mili. Userbot set karo.")

    async with upload_lock:
        wait_msg = await message.reply_text("🔎 **Searching Message...**")
        try:
            # Link Cleaning
            link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = link.split("/")
            
            # Logic to find Chat ID and Message ID
            chat_id = None
            msg_id = None

            # Handle: t.me/c/123456789/100 (Private)
            if parts[0] == "c":
                chat_id = int("-100" + parts[1])
                msg_id = int(parts[-1].split("?")[0]) # Remove ?single etc
            
            # Handle: t.me/username/100 (Public)
            # Handle: t.me/username/topic_id/100 (Topic)
            else:
                chat_id = parts[0]
                # Last part is always message ID
                msg_id = int(parts[-1].split("?")[0])

            # Fetch via Userbot
            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if not target_msg or target_msg.empty:
                await wait_msg.edit("❌ Message nahi mila. Kya Userbot us channel mein hai?")
                return

            # Check Media
            media = None
            if target_msg.video: media = target_msg.video
            elif target_msg.document: media = target_msg.document
            elif target_msg.photo: media = target_msg.photo
            
            if not media:
                await wait_msg.edit("❌ Is link par koi Video/File nahi mili.")
                return

            await wait_msg.delete()
            # Process using the Userbot message object
            await process_media(media, message, original_msg=target_msg)

        except Exception as e:
            await wait_msg.edit(f"❌ **Error:** `{e}`\nCheck karo link sahi hai ya Userbot joined hai.")

# --- START COMMAND ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready!**\n- Send Video/PDF directly.\n- Send Public/Private Link (Userbot Active).")

# --- MAIN LOOP ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("✅ Main Bot Starting...")
    await bot.start()
    
    if userbot:
        print("✅ Userbot Starting...")
        try:
            await userbot.start()
        except Exception as e:
            print(f"⚠️ Userbot Fail: {e}")
    
    await asyncio.Event().wait() # Keep running

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
