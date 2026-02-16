import os
import time
import uuid
import threading
import requests
import logging
import shutil
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- SERVER KEEPER (Render ko sone nahi dega) ---
app = Flask(__name__)
@app.route('/')
def home(): return "PixelDrain Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bot Setup
bot = Client("pd_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=2)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

# --- PIXELDRAIN UPLOAD FUNCTION ---
def upload_to_pixeldrain(file_path, file_name):
    url = "https://pixeldrain.com/api/file/"
    try:
        # File open karke upload karna
        with open(file_path, 'rb') as f:
            response = requests.post(
                url,
                data=f,
                auth=('', ''), # Anonymous upload (Account ki zarurat nahi)
                params={'name': file_name}
            )
        
        if response.status_code == 201:
            data = response.json()
            file_id = data['id']
            # Direct link format
            return f"https://pixeldrain.com/api/file/{file_id}"
        else:
            return None
    except Exception as e:
        print(f"Upload Error: {e}")
        return None

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Ready!**\nFile bhejo, main PixelDrain ka Direct Link dunga (Fast & Secure).")

@bot.on_message(filters.video | filters.document)
async def handle_file(client, message):
    try:
        media = message.video or message.document
        if not media: return

        # 1. File Name Logic
        if message.video:
            original_name = f"video_{uuid.uuid4().hex[:5]}.mp4"
        else:
            original_name = media.file_name or f"file_{uuid.uuid4().hex[:5]}.pdf"

        # Safai
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        file_size = get_readable_size(media.file_size)

        status = await message.reply_text(f"⏳ **Processing...**\n`{safe_name}`")

        # 2. Download Path
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{safe_name}"

        # 3. Download
        await status.edit("⬇️ **Downloading...**")
        await message.download(file_name=local_path)

        # 4. Upload to PixelDrain
        await status.edit("⬆️ **Uploading to PixelDrain...**\n(Ye fast hoga)")
        
        # Thread mein upload taaki bot hang na ho
        direct_link = await bot.loop.run_in_executor(None, upload_to_pixeldrain, local_path, safe_name)

        if direct_link:
            # 5. Success Reply
            if message.video:
                msg = f"✅ **Video Uploaded!**\n\n🔗 **Direct Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"
                btn = InlineKeyboardButton("🎬 Play Video", url=direct_link)
            else:
                msg = f"✅ **PDF Uploaded!**\n\n🔗 **Direct Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"
                btn = InlineKeyboardButton("📄 Open PDF", url=direct_link)

            await status.delete()
            await message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))
        else:
            await status.edit("❌ **Upload Failed!** PixelDrain server issue.")

    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

    finally:
        # 6. Cleanup (Space bachane ke liye)
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
