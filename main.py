import os
import time
import uuid
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

# --- RENDER PORT FIX ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_flask():
    # Render default port 10000 use karta hai ya PORT env se leta hai
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
# -----------------------

# Config
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 **Hi! Main taiyar hoon.**\n\n"
        "Bade files (400MB+) Archive.org pe upload karne ke liye mujhe Video ya PDF bhejo."
    )

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    
    # Details nikalna
    file_name = getattr(media, "file_name", f"file_{uuid.uuid4().hex[:5]}")
    file_size = get_readable_size(media.file_size)
    duration = getattr(media, "duration", 0)
    
    status = await message.reply_text(f"📥 **Downloading...**\n`{file_name}`\nSize: {file_size}")

    # Local Path setup
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    local_path = os.path.join("downloads", f"{uuid.uuid4().hex}_{file_name}")
    
    try:
        # 1. Download
        path = await message.download(file_name=local_path)
        
        await status.edit(f"📤 **Uploading to Archive.org...**\nSize: {file_size}")

        # 2. Archive Upload
        identifier = f"bot_up_{uuid.uuid4().hex[:10]}"
        
        meta = {
            'mediatype': 'movies' if message.video else 'texts',
            'title': file_name,
            'description': f'Uploaded via Telegram Bot. Size: {file_size}'
        }

        upload(
            identifier,
            files=[path],
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata=meta
        )

        # 3. Links
        encoded_name = file_name.replace(" ", "%20")
        direct_link = f"https://archive.org/download/{identifier}/{encoded_name}"
        viewer_link = f"https://archive.org/details/{identifier}"

        # 4. Final Message
        res = (
            f"✅ **Upload Success!**\n\n"
            f"📄 **Name:** `{file_name}`\n"
            f"📦 **Size:** {file_size}\n"
        )
        if message.video:
            res += f"⏳ **Duration:** {duration}s\n"

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Open in Browser / Chrome", url=direct_link)],
            [InlineKeyboardButton("📂 Archive Page", url=viewer_link)]
        ])

        await status.delete()
        await message.reply_text(res, reply_markup=btn)

    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}")
    
    finally:
        # 5. Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    # Flask ko alag thread mein chalana taaki Render port error na de
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Bot starting...")
    bot.run()
