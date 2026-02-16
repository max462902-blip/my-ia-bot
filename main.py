import os
import re
import uuid
import threading
import urllib.parse  # Link encoding ke liye
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

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
    # Archive identifier sirf alphanumeric aur underscore allow karta hai
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:40]

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ Bot Ready! Badi video ya PDF bhejein.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    if not media: return

    orig_name = getattr(media, "file_name", "file")
    # File name se spaces aur brackets hatana safety ke liye (Optional but recommended)
    safe_file_name = orig_name.replace(" ", "_").replace("(", "").replace(")", "")
    
    file_size = get_readable_size(media.file_size)
    duration = getattr(media, "duration", 0)
    
    status = await message.reply_text(f"⏳ **Downloading...** `{orig_name}`")

    # Identifier banana
    identifier = f"{clean_id(orig_name)}_{uuid.uuid4().hex[:5]}"
    local_path = f"./downloads/{uuid.uuid4().hex}_{safe_file_name}"
    
    if not os.path.exists("downloads"): os.makedirs("downloads")

    try:
        # 1. Download
        path = await message.download(file_name=local_path)
        await status.edit("📤 **Archive.org par upload ho raha hai...**\n(Isme thoda time lag sakta hai)")

        # 2. Upload
        upload(
            identifier,
            files={safe_file_name: path}, # Sahi filename map karna
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={'mediatype': 'movies' if message.video else 'texts', 'title': orig_name}
        )

        # 3. Encoding fix (Brackets aur Spaces ke liye)
        encoded_name = urllib.parse.quote(safe_file_name)
        direct_url = f"https://archive.org/download/{identifier}/{encoded_name}"
        details_url = f"https://archive.org/details/{identifier}"
        
        # 4. Final Response
        res_text = (
            f"✅ **Upload Success!**\n\n"
            f"🔗 **Admin Direct Link (Copy this):**\n`{direct_url}`\n\n"
            f"⚠️ **Note:** Agar link 'Page Not Found' dikhaye, toh 2-5 minute wait karein, Archive use process kar raha hai.\n\n"
            f"📦 **Size:** {file_size}"
        )
        if message.video: res_text += f"\n⏳ **Length:** {duration} sec"

        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Open in Chrome", url=direct_url)],
            [InlineKeyboardButton("📂 View Archive Page", url=details_url)]
        ])

        await status.delete()
        await message.reply_text(res_text, reply_markup=btns)

    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}")
    
    finally:
        if os.path.exists(local_path): os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
