from flask import Flask
from threading import Thread
import os
import random
import requests  # Naya library add kiya
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

# YouTube Download Function (Bina Cookies wala Easy Tarika)
def download_youtube_video(url):
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "accept": "application/json",
        "content-type": "application/json"
    }
    # Quality 720p rakhi hai taaki Render ki storage full na ho
    payload = {"url": url, "vQuality": "720"}

    try:
        # Step 1: Cobalt API se direct link lena
        response = requests.post(api_url, headers=headers, json=payload)
        data = response.json()
        
        if "url" not in data:
            return None
        
        video_direct_link = data["url"]
        
        # Step 2: Video download karna
        file_path = f"downloads/video_{random.randint(100, 999)}.mp4"
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
            
        r = requests.get(video_direct_link, stream=True)
        with open(file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        
        return file_path
    except Exception as e:
        print(f"Error: {e}")
        return None

@app_bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bhai! Mujhe Video file bhejo ya YouTube link, main Archive par upload kar dunga. (No Cookies Required!)")

# 1. YouTube Link Handler
@app_bot.on_message(filters.text & filters.regex(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"))
async def handle_youtube_link(client, message):
    try:
        url = message.text
        status_msg = await message.reply_text("🔎 YouTube link mil gaya! Bina cookies ke bypass kar raha hoon...")
        
        # Download logic
        file_path = download_youtube_video(url)
        
        if file_path:
            await process_to_archive(status_msg, file_path, message.chat.id)
        else:
            await status_msg.edit_text("❌ YouTube ne block kar diya ya link galat hai. Dobara try karein.")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# 2. Video/Document Handler
@app_bot.on_message(filters.video | filters.document)
async def handle_video_file(client, message):
    try:
        status_msg = await message.reply_text("⬇️ File download ho rahi hai...")
        file_path = await message.download()
        await process_to_archive(status_msg, file_path, message.chat.id)
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Common Upload Function
async def process_to_archive(status_msg, file_path, chat_id):
    try:
        await status_msg.edit_text("⬆️ Uploading to Archive... (Sabar rakho)")

        unique_id = random.randint(1000, 99999)
        identifier = f"ia_up_{chat_id}_{unique_id}"
        
        # Archive Upload
        upload(identifier, files=[file_path], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        filename = os.path.basename(file_path)
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ **Upload Success!**\n\n"
                   f"🔗 Details Page:\n{details_link}\n\n"
                   f"🎬 Direct Stream Link:\n{stream_link}")
        
        await status_msg.edit_text(caption)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload Error: {str(e)}")

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    keep_alive()
    app_bot.run()
