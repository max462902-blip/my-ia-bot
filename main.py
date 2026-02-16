import os
import re
import uuid
import threading
import urllib.parse
import gc  # Garbage Collector for RAM
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

# --- SERVER KEEPER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Alive"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

# Workers kam kiye taaki RAM bache
bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=2)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def clean_id(text):
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:30]

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bot Alive. Send file.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    if not media: return

    # RAM check - 500MB se upar file risk hai free server pe
    if media.file_size > 500 * 1024 * 1024:
        return await message.reply_text("❌ File too big for Free Render Plan (Limit: 500MB)")

    orig_name = getattr(media, "file_name", "video.mp4" if message.video else "file.pdf")
    # File name safai for URL
    safe_name = re.sub(r'[\\/*?:"<>|()\s]', '_', orig_name)
    
    status = await message.reply_text(f"⬇️ **Downloading...**")

    # Paths
    if not os.path.exists("downloads"): os.makedirs("downloads")
    identifier = f"{clean_id(safe_name)}_{uuid.uuid4().hex[:5]}"
    local_path = os.path.abspath(f"downloads/{safe_name}")

    try:
        # 1. Download
        await message.download(file_name=local_path)
        await status.edit("⬆️ **Uploading...**")
        
        # Memory cleanup after download
        gc.collect() 

        # 2. Upload
        upload(
            identifier,
            files={safe_name: local_path},
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={'mediatype': 'movies' if message.video else 'texts', 'title': orig_name},
            verbose=True
        )

        # 3. Link Generation
        # URL Encoding zaroori hai Chrome ke liye
        encoded_name = urllib.parse.quote(safe_name)
        direct_url = f"https://archive.org/download/{identifier}/{encoded_name}"
        
        # 4. Response
        if message.video:
            btn_text = "🎬 Stream Video"
            msg_text = f"✅ **Done!**\n🔗 `{direct_url}`"
        else:
            btn_text = "📄 Open PDF"
            msg_text = f"✅ **Done!**\n🔗 `{direct_url}`"

        await status.delete()
        await message.reply_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=direct_url)]])
        )

    except Exception as e:
        print(f"Error: {e}")
        await status.edit(f"❌ Error: {e}")

    finally:
        # 5. HARD DELETE & MEMORY CLEAN
        if os.path.exists(local_path):
            os.remove(local_path)
        
        # Variables delete karke RAM free karna
        del local_path
        del identifier
        gc.collect()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
