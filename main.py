from flask import Flask
from threading import Thread
import os
import random
import requests
import re
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

# --- Setup ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SESSION_STRING = os.environ.get("SESSION_STRING")
IA_ACCESS = os.environ.get("IA_ACCESS")
IA_SECRET = os.environ.get("IA_SECRET")

# Bot Client
app_bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# User Client (Aapka Account)
app_user = Client("my_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# YouTube Download Function
def download_youtube_video(url):
    api_url = "https://api.cobalt.tools/api/json"
    headers = {"accept": "application/json", "content-type": "application/json"}
    payload = {"url": url, "vQuality": "720"}
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        video_direct_link = response.json().get("url")
        if not video_direct_link:
            return None
        
        file_path = f"downloads/yt_{random.randint(100, 999)}.mp4"
        if not os.path.exists("downloads"):
            os.makedirs("downloads")
            
        r = requests.get(video_direct_link, stream=True)
        with open(file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return file_path
    except:
        return None

@app_bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bhai! Link bhejo, main Archive par upload kar dunga.")

# 1. Restricted Telegram Link Handler
@app_bot.on_message(filters.text & filters.regex(r"https://t.me/c/(\d+)/(\d+)"))
async def handle_restricted_link(client, message):
    try:
        status_msg = await message.reply_text("📥 Restricted Link mila! Download ho raha hai...")
        
        match = re.search(r"https://t.me/c/(\d+)/(\d+)", message.text)
        chat_id = int("-100" + match.group(1))
        msg_id = int(match.group(2))

        async with app_user:
            msg = await app_user.get_messages(chat_id, msg_id)
            file_path = await app_user.download_media(message=msg)

        if file_path:
            await process_to_archive(status_msg, file_path, message.chat.id)
        else:
            await status_msg.edit_text("❌ Download fail ho gaya.")
    except Exception as e:
        await message.reply_text(f"❌ Userbot Error: {str(e)}")

# 2. YouTube Link Handler
@app_bot.on_message(filters.text & filters.regex(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"))
async def handle_youtube_link(client, message):
    status_msg = await message.reply_text("🔎 YouTube link mil gaya! Download ho raha hai...")
    file_path = download_youtube_video(message.text)
    if file_path:
        await process_to_archive(status_msg, file_path, message.chat.id)
    else:
        await status_msg.edit_text("❌ YouTube Download fail!")

# 3. File Handler
@app_bot.on_message(filters.video | filters.document)
async def handle_video_file(client, message):
    status_msg = await message.reply_text("⬇️ File download ho rahi hai...")
    file_path = await message.download()
    await process_to_archive(status_msg, file_path, message.chat.id)

# Common Upload Function
async def process_to_archive(status_msg, file_path, chat_id):
    try:
        await status_msg.edit_text("⬆️ Uploading to Archive...")
        unique_id = random.randint(1000, 99999)
        identifier = f"ia_up_{chat_id}_{unique_id}"
        
        # Archive Upload
        upload(identifier, files=[file_path], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        filename = os.path.basename(file_path)
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ **Upload Success!**\n\n"
                   f"🔗 Details: {details_link}\n"
                   f"🎬 Direct: {stream_link}")
        
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
        filename = os.path.basename(file_path)
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        await status_msg.edit_text(f"✅ **Success!**\n\n🔗 Details: {details_link}\n🎬 Direct: {stream_link}")
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload Error: {str(e)}")

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    keep_alive()
    app_bot.run()        
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
