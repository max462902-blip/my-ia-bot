import os
import re
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
def home(): return "Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT CONFIG ---
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

def clean_name(text):
    # Archive.org identifier sirf alphanumeric allow karta hai
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:40]

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ Bot Active Hai! Video ya PDF bhejo.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    if not media: return

    orig_file_name = getattr(media, "file_name", "file")
    file_size = get_readable_size(media.file_size)
    duration = getattr(media, "duration", 0)
    
    status = await message.reply_text(f"⏳ **Processing:** `{orig_file_name}`...")

    # Unique identifier banana
    clean_id = clean_name(orig_file_name)
    identifier = f"{clean_id}_{uuid.uuid4().hex[:5]}"
    
    local_path = f"./downloads/{uuid.uuid4().hex}_{orig_file_name}"
    if not os.path.exists("downloads"): os.makedirs("downloads")

    try:
        # 1. Download
        path = await message.download(file_name=local_path)
        await status.edit("📤 **Archive.org pe upload ho raha hai...**")

        # 2. Upload
        upload(
            identifier,
            files=[path],
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata={
                'mediatype': 'movies' if message.video else 'texts',
                'title': orig_file_name
            }
        )

        # 3. Direct Link taiyar karna (Chrome/Admin ke liye)
        encoded_name = orig_file_name.replace(" ", "%20")
        direct_url = f"https://archive.org/download/{identifier}/{encoded_name}"
        
        # 4. Final Message Layout
        if message.video:
            info_text = f"🎬 **Video Details:**\n📦 **Size:** {file_size}\n⏳ **Length:** {duration} sec"
            btn_label = "🎥 Watch Online / Direct Link"
        else:
            info_text = f"📄 **PDF Details:**\n📦 **Size:** {file_size}"
            btn_label = "📖 Open PDF / Direct Link"

        final_response = (
            f"✅ **Successfully Uploaded!**\n\n"
            f"🔗 **Direct Link for Admin:**\n`{direct_url}`\n\n"
            f"{info_text}"
        )

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_label, url=direct_url)],
            [InlineKeyboardButton("📂 Archive Page", url=f"https://archive.org/details/{identifier}")]
        ])

        await status.delete()
        await message.reply_text(final_response, reply_markup=reply_markup)

    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}")
    
    finally:
        if os.path.exists(local_path): os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
