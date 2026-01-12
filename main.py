from flask import Flask
from threading import Thread
import os
import random
from pyrogram import Client, filters
from internetarchive import upload

# --- Web Server (Bot ko zinda rakhne ke liye) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Bot Setup (Pyrogram) ---
# Render Environment se variables lega
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
IA_ACCESS = os.environ.get("IA_ACCESS")
IA_SECRET = os.environ.get("IA_SECRET")

# Client Start
app_bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app_bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bhai! Badi video bhejo (2GB tak), main Archive par daal dunga.")

@app_bot.on_message(filters.video | filters.document)
async def handle_video(client, message):
    try:
        status_msg = await message.reply_text("⬇️ Downloading... (Ye badi file hai, time lagega)")
        
        # Pyrogram se badi file download ho jayegi
        file_path = await message.download()
        
        await status_msg.edit_text("⬆️ Uploading to Archive... (Sabar rakho)")

        # Random Identifier taaki error na aaye
        unique_id = random.randint(1000, 99999)
        identifier = f"ia_up_{message.chat.id}_{unique_id}"
        
        # Upload to Archive
        upload(identifier, files=[file_path], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        # Links
        filename = file_path.split("/")[-1]
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ **Upload Success!**\n\n"
                   f"🔗 [Details Page]({details_link})\n"
                   f"🎬 [Direct Stream Link]({stream_link})\n\n"
                   f"__Note: Link 5-10 min baad chalega.__")
        
        await status_msg.edit_text(caption, disable_web_page_preview=True)
        
        # File delete server se
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# Bot Run
if __name__ == "__main__":
    keep_alive()
    app_bot.run()
