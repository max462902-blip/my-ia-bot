import os
import time
import uuid
import shutil
import logging
import asyncio
import threading
import urllib.parse
from flask import Flask
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

# --- SETUP & LOGGING ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- BOT CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

# Workers kam rakhe hain taaki RAM full na ho
bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=1)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ Bot Ready! Video forward karo ya upload karo ya pdf send kro.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    try:
        # Step 1: Message Receive hote hi Log print karo (Render Logs check karna)
        print(f"New Message Received from {message.chat.id}")
        
        media = message.video or message.document
        if not media: return

        # --- FIX: FILE NAME HANDLING ---
        # Agar video hai toh uska koi naam nahi hota, hum khud banayenge
        if message.video:
            # Random naam generate karna zaroori hai
            file_ext = "mp4"
            original_name = f"video_{uuid.uuid4().hex[:5]}.{file_ext}"
            mime_type = "video/mp4"
        else:
            # Document ka naam hota hai
            original_name = media.file_name or f"file_{uuid.uuid4().hex[:5]}.pdf"
            mime_type = media.mime_type or "application/pdf"

        # Safai (Spaces aur Brackets hatana)
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        file_size = get_readable_size(media.file_size)

        # Step 2: User ko Reply
        status = await message.reply_text(f"⏳ **Processing...**\n📂 `{safe_name}`\n📦 {file_size}")

        # Local Path
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{safe_name}"

        # Step 3: Download
        await status.edit("⬇️ **Downloading...**")
        await message.download(file_name=local_path)

        # Step 4: Upload to Archive
        await status.edit("⬆️ **Uploading to Archive.org...**")
        
        identifier = f"vid_{uuid.uuid4().hex[:8]}" # Unique ID for Archive
        
        # Upload process (Async Thread mein taaki bot hang na ho)
        await asyncio.to_thread(
            upload,
            identifier,
            files={safe_name: local_path},
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={'mediatype': 'movies' if message.video else 'texts', 'title': safe_name},
            verbose=False
        )

        # Step 5: Generate Link
        encoded_name = urllib.parse.quote(safe_name)
        direct_link = f"https://archive.org/download/{identifier}/{encoded_name}"

        # Step 6: Final Reply
        if message.video:
            btn_text = "🎬 Play Video / Download"
            reply_text = f"✅ **Video Uploaded!**\n\n🔗 **Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"
        else:
            btn_text = "📄 Open PDF"
            reply_text = f"✅ **PDF Uploaded!**\n\n🔗 **Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"

        await status.delete()
        await message.reply_text(
            reply_text, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=direct_link)]])
        )

    except Exception as e:
        print(f"ERROR: {e}")
        # Agar message delete ho chuka hai toh naya bhej do
        try:
            await status.edit(f"❌ Error: {str(e)}")
        except:
            await message.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        # Step 7: Delete Local File (Important for Render 512MB RAM)
        if 'local_path' in locals() and os.path.exists(local_path):
            os.remove(local_path)
            print("Cleanup Done.")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
