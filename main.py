import os
import re
import uuid
import threading
import time
import asyncio
import urllib.parse
import gc
from flask import Flask
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

# --- SERVER KEEPER (FLASK) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Alive & Running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

# Workers limited to 1 to save RAM
bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=1)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def clean_id(text):
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:30]

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ Bot is Online! files bhejte waqt dhairya rakhein.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    if not media: return

    # RAM Safety Check (400MB Limit recommended for Free Tier)
    if media.file_size > 400 * 1024 * 1024:
        return await message.reply_text("❌ File 400MB se badi hai. Render Free Plan crash ho jayega.")

    orig_name = getattr(media, "file_name", "video.mp4" if message.video else "file.pdf")
    safe_name = re.sub(r'[\\/*?:"<>|()\s]', '_', orig_name)
    
    status = await message.reply_text(f"⬇️ **Download हो रहा है थोड़ा सा इंतजार करें...**")

    # Paths
    if not os.path.exists("downloads"): os.makedirs("downloads")
    identifier = f"{clean_id(safe_name)}_{uuid.uuid4().hex[:5]}"
    local_path = os.path.abspath(f"downloads/{safe_name}")

    try:
        # 1. Download
        await message.download(file_name=local_path)
        await status.edit("⬆️ **Upload हो रहा है थोड़ा सा इंतजार करें..**")
        gc.collect() # RAM saaf karna

        # 2. Upload
        # Run in executor because 'upload' library is blocking
        await asyncio.to_thread(
            upload,
            identifier,
            files={safe_name: local_path},
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={'mediatype': 'movies' if message.video else 'texts', 'title': orig_name},
            verbose=False
        )

        # 3. Link Generation
        encoded_name = urllib.parse.quote(safe_name)
        direct_url = f"https://archive.org/download/{identifier}/{encoded_name}"
        
        # 4. Response
        if message.video:
            msg_text = f"✅ **Video Uploaded!**\n🔗 `{direct_url}`"
            btn = InlineKeyboardButton("🎬 Stream Video", url=direct_url)
        else:
            msg_text = f"✅ **PDF Uploaded!**\n🔗 `{direct_url}`"
            btn = InlineKeyboardButton("📄 Open PDF", url=direct_url)

        await status.delete()
        await message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup([[btn]]))

    except errors.FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text(f"⚠️ Flood Wait: {e.value} seconds rukein.")
    except Exception as e:
        print(f"Error: {e}")
        await status.edit(f"❌ Error: {str(e)[:100]}")

    finally:
        # 5. HARD DELETE
        if os.path.exists(local_path):
            os.remove(local_path)
        gc.collect()

if __name__ == "__main__":
    # Flask thread start
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Auto-Reconnect Logic for FloodWait
    print("Bot starting...")
    while True:
        try:
            bot.run()
            break
        except errors.FloodWait as e:
            print(f"FloodWait detected. Sleeping for {e.value} seconds...")
            time.sleep(e.value + 1)
        except Exception as e:
            print(f"Critical Error: {e}")
            time.sleep(5)
