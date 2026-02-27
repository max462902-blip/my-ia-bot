import os
import threading
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

# --- FLASK SERVER (RENDER KE LIYE NAKLI WEBSITE) ---
# Ye code Render ko batayega ki humara server zinda hai aur PORT open hai
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is Running! 🚀"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- TELEGRAM BOT CODE ---
app = Client("pdf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def upload_to_catbox(file_path):
    url = "https://catbox.moe/user/api.php"
    data = {"reqtype": "fileupload", "userhash": ""}
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": f}
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                return response.text
            else:
                return None
    except Exception as e:
        print(f"Error uploading: {e}")
        return None

@app.on_message(filters.document | filters.video | filters.audio)
async def handle_document(client, message):
    if message.document and message.document.file_size > 400 * 1024 * 1024:
        await message.reply_text("❌ फाइल 400MB से बड़ी है।")
        return

    status_msg = await message.reply_text("📥 **Downloading...**\n\nRender पर आ रहा है...")
    
    file_path = None
    try:
        file_path = await message.download()
        await status_msg.edit_text("📤 **Uploading to Cloud...**")
        
        link = upload_to_catbox(file_path)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if link and "catbox" in link:
            caption = (
                f"✅ **File Uploaded!**\n\n"
                f"📂 **Name:** `{message.document.file_name if message.document else 'File'}`\n\n"
                f"🔗 **Link (Tap Copy):**\n`{link}`"
            )
            button = InlineKeyboardMarkup([[InlineKeyboardButton("📂 Open File", url=link)]])
            await status_msg.edit_text(caption, reply_markup=button)
        else:
            await status_msg.edit_text("❌ अपलोड फेल हो गया।")
            
    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.edit_text(f"Error: {e}")

# --- START BOT AND SERVER ---
if __name__ == "__main__":
    # Server ko alag thread me start karo
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    # Bot start karo
    print("Bot Starting...")
    app.run()
