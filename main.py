import os
import time
import threading
from flask import Flask
from pyrogram import Client, filters
from github import Github

# --- 1. WEB SERVER (Render ko zinda rakhne ke liye) ---
web_server = Flask(__name__)

@web_server.route('/')
def home():
    return "Bot is Running smoothly!"

def run_web_server():
    # Render ka diya hua PORT use karega
    port = int(os.environ.get("PORT", 8080))
    web_server.run(host='0.0.0.0', port=port)

def start_server():
    t = threading.Thread(target=run_web_server)
    t.start()

# --- 2. BOT SETTINGS ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO")

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
git = Github(GITHUB_TOKEN)

@app.on_message(filters.document | filters.video)
async def handle_files(client, message):
    status_msg = await message.reply_text("📥 Downloading...", quote=True)

    try:
        # Download
        file_path = await message.download()
        file_name = os.path.basename(file_path)
        unique_name = f"{int(time.time())}_{file_name}"

        # Upload
        await status_msg.edit("☁️ Uploading to GitHub...")
        repo = git.get_repo(GITHUB_REPO_NAME)
        
        with open(file_path, "rb") as f:
            content = f.read()
        
        repo.create_file(unique_name, f"Upload {unique_name}", content)

        # Links
        raw_link = f"https://raw.githubusercontent.com/{GITHUB_REPO_NAME}/main/{unique_name}".replace(" ", "%20")
        cdn_link = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO_NAME}/{unique_name}".replace(" ", "%20")
        
        final_link = raw_link
        display_text = "🔗 File Link"

        # Link Type Logic
        if file_name.lower().endswith(".pdf"):
            final_link = f"https://docs.google.com/viewer?url={raw_link}&embedded=true"
            display_text = "📄 **View PDF**"
        elif file_name.lower().endswith((".mp4", ".mkv")):
            final_link = cdn_link
            display_text = "🎥 **Watch Video**"

        await status_msg.edit(
            f"✅ **Done!**\n\n{display_text}:\n{final_link}"
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {e}")
    
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 3. START EVERYTHING ---
if __name__ == "__main__":
    print("Starting Web Server...")
    start_server()  # Ye line Render ka Port Error theek karegi
    print("Starting Bot...")
    app.run()
