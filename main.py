from flask import Flask
from threading import Thread
import os
import random
import yt_dlp  # Naya library add kiya
from pyrogram import Client, filters
from internetarchive import upload

# --- Web Server ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Bot Setup ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
IA_ACCESS = os.environ.get("IA_ACCESS")
IA_SECRET = os.environ.get("IA_SECRET")

app_bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# YouTube Download Function
def download_youtube_video(url):
    ydl_opts = {
        'format': 'best[ext=mp4]/best', # MP4 format priority
        'outtmpl': 'downloads/%(title)s.%(ext)s', # Downloads folder mein save hoga
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

@app_bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bhai! Mujhe Video file bhejo ya YouTube link, main Archive par upload kar dunga.")

# 1. YouTube Link Handler
@app_bot.on_message(filters.text & filters.regex(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"))
async def handle_youtube_link(client, message):
    try:
        url = message.text
        status_msg = await message.reply_text("🔎 YouTube link mil gaya! Download ho raha hai...")
        
        # Step 1: Download from YouTube
        file_path = download_youtube_video(url)
        
        # Step 2: Upload to Archive (Common Logic)
        await process_to_archive(status_msg, file_path, message.chat.id)

    except Exception as e:
        await message.reply_text(f"❌ YouTube Error: {str(e)}")

# 2. Video/Document Handler
@app_bot.on_message(filters.video | filters.document)
async def handle_video_file(client, message):
    try:
        status_msg = await message.reply_text("⬇️ File download ho rahi hai...")
        
        # Step 1: Download from Telegram
        file_path = await message.download()
        
        # Step 2: Upload to Archive
        await process_to_archive(status_msg, file_path, message.chat.id)

    except Exception as e:
        await message.reply_text(f"❌ Telegram Download Error: {str(e)}")

# Common Upload Function
async def process_to_archive(status_msg, file_path, chat_id):
    try:
        await status_msg.edit_text("⬆️ Uploading to Archive... (Sabar rakho)")

        unique_id = random.randint(1000, 99999)
        identifier = f"ia_up_{chat_id}_{unique_id}"
        
        # IA Upload
        upload(identifier, files=[file_path], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        filename = os.path.basename(file_path)
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ **Upload Success!**\n\n"
                   f"🔗 Details Page:\n{details_link}\n\n"
                   f"🎬 Direct Stream Link:\n{stream_link}\n\n"
                   f"__Note: Link 5-10 min baad chalega.__")
        
        await status_msg.edit_text(caption)
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload Error: {str(e)}")

# Bot Run
if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    keep_alive()
    app_bot.run()
