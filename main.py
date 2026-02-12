import os
import time
import threading
import re
from flask import Flask
from pyrogram import Client, filters
from github import Github

# --- 1. WEB SERVER (Render ko active rakhne ke liye) ---
web_server = Flask(__name__)
@web_server.route('/')
def home(): return "Rojgarclass Bot is Live!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_server.run(host='0.0.0.0', port=port)

# --- 2. BOT CONFIGURATION ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO")

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
git = Github(GITHUB_TOKEN)

# --- 3. START COMMAND HANDLER ---
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_name = message.from_user.first_name
    welcome_text = (
        f"नमस्ते {user_name}! 👋\n\n"
        "मैं **Rojgarclass Direct Link Bot** हूँ।\n\n"
        "मुझे कोई भी **PDF** या **MP4 Video** भेजें, "
        "मैं उसे test guru server पर अपलोड करके आपको **Direct Link** दे दूँगा "
        "जिसे आप अपने App के Admin Panel में इस्तेमाल कर सकते हैं।\n\n"
        "⚠️ **सीमा:** फाइल का साइज़ 100MB से कम होना चाहिए।"
    )
    await message.reply_text(welcome_text)

# --- 4. FILE UPLOAD HANDLER ---
@app.on_message(filters.document | filters.video)
async def handle_files(client, message):
    status_msg = await message.reply_text("📥 फाइल डाउनलोड हो रही है...", quote=True)

    try:
        # File Download
        file_path = await message.download()
        raw_name = os.path.basename(file_path)

        # File Name Clean Up (Spaces aur Brackets hatana zaroori hai)
        clean_name = re.sub(r'[^a-zA-Z0-9.]', '_', raw_name)
        unique_name = f"{int(time.time())}_{clean_name}"

        # Upload to GitHub
        await status_msg.edit("📤 server पर अपलोड हो रहा है...")
        repo = git.get_repo(GITHUB_REPO_NAME)
        with open(file_path, "rb") as f:
            content = f.read()
        repo.create_file(unique_name, f"Upload {unique_name}", content)

        # DIRECT CDN LINK (Best for Apps)
        direct_link = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO_NAME}@main/{unique_name}"

        # Final Response
        await status_msg.edit(
            f"✅ **अपलोड सफल!**\n\n"
            f"📄 **Direct Link:**\n`{direct_link}`\n\n"
            f"इसे अपने Admin Panel में पेस्ट करें।"
        )

    except Exception as e:
        await status_msg.edit(f"❌ एरर आया: {str(e)}")
    
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 5. RUN BOT AND SERVER ---
if __name__ == "__main__":
    print("Starting Web Server...")
    threading.Thread(target=run_web_server).start()
    print("Starting Bot...")
    app.run()
