import os
import re
import uuid
import threading
import urllib.parse
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

# --- RENDER PORT FIX ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

def clean_id(text):
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:40]

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ Bot Active Hai! Video ya PDF bhejo.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    if not media: return

    # Check for 512MB Limit (Safe side)
    if media.file_size > 480 * 1024 * 1024:
        return await message.reply_text("❌ File bahut badi hai! main sirf 480MB tak handle kar sakta hu.")

    orig_name = getattr(media, "file_name", "video.mp4" if message.video else "file.pdf")
    safe_file_name = orig_name.replace(" ", "_").replace("(", "").replace(")", "")
    file_size = get_readable_size(media.file_size)
    
    status = await message.reply_text(f"⏳ **Downloading:** `{orig_name}`...")

    # Unique Identifier & Local Path
    identifier = f"{clean_id(orig_name)}_{uuid.uuid4().hex[:5]}"
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = os.path.abspath(f"downloads/{uuid.uuid4().hex[:8]}_{safe_file_name}")
    
    try:
        # 1. Download
        path = await message.download(file_name=local_path)
        await status.edit("📤 **Uploading to server...**")

        # 2. Upload to Archive
        upload(
            identifier,
            files={safe_file_name: path},
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={'mediatype': 'movies' if message.video else 'texts', 'title': orig_name}
        )

        # 3. URL Encoding
        encoded_name = urllib.parse.quote(safe_file_name)
        direct_url = f"https://archive.org/download/{identifier}/{encoded_name}"
        
        # 4. Success Message (Conditions applied)
        if message.video:
            res_text = f"✅ **Video Uploaded!**\n\n🔗 **Direct Link:**\n`{direct_url}`\n\n📦 **Size:** {file_size}"
            btn_label = "🎬 Watch Online"
        else:
            res_text = f"✅ **PDF Uploaded!**\n\n🔗 **Direct Link:**\n`{direct_url}`\n\n📦 **Size:** {file_size}"
            btn_label = "📖 Open PDF"

        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_label, url=direct_url)],
            [InlineKeyboardButton("📂 View Archive Page", url=f"https://archive.org/details/{identifier}")]
        ])

        await status.delete()
        await message.reply_text(res_text, reply_markup=btns)

    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}")
    
    finally:
        # --- CRITICAL CLEANUP ---
        # Ye part file ko 100% delete karega chahe upload ho ya fail
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"🗑️ Cleanup: Local file deleted to save space: {local_path}")
        else:
            print("ℹ️ Cleanup: No local file found to delete.")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
