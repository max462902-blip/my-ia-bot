import os
import time
from pyrogram import Client, filters
from github import Github

# --- Configuration ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO") 

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
git = Github(GITHUB_TOKEN)

@app.on_message(filters.document | filters.video)
async def handle_files(client, message):
    status_msg = await message.reply_text("📥 Downloading to Server...")

    try:
        # 1. Download
        file_path = await message.download()
        file_name = os.path.basename(file_path)
        
        # Unique Name logic
        unique_name = f"{int(time.time())}_{file_name}"

        # 2. Upload to GitHub
        await status_msg.edit("☁️ Uploading to GitHub...")
        repo = git.get_repo(GITHUB_REPO_NAME)
        
        with open(file_path, "rb") as f:
            content = f.read()
            
        repo.create_file(unique_name, f"Upload {unique_name}", content)

        # --- MAIN LOGIC FOR LINKS ---
        
        # GitHub ka Raw Link (Base Link)
        raw_github_link = f"https://raw.githubusercontent.com/{GITHUB_REPO_NAME}/main/{unique_name}"
        raw_github_link = raw_github_link.replace(" ", "%20") # Space fix

        # JsDelivr Link (Fast Loading & Streaming ke liye)
        # Format: https://cdn.jsdelivr.net/gh/USER/REPO/FILE
        cdn_link = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO_NAME}/{unique_name}"
        cdn_link = cdn_link.replace(" ", "%20")

        final_link_to_give = ""
        
        # Agar PDF hai -> Google Docs Viewer Link banao
        if file_name.lower().endswith(".pdf"):
            # Google Viewer magic link
            final_link_to_give = f"https://docs.google.com/viewer?url={raw_github_link}&embedded=true"
            display_text = "📄 **View PDF Online (No Download)**"
            
        # Agar Video hai -> JsDelivr Link do (Taaki stream ho sake)
        elif file_name.lower().endswith((".mp4", ".mkv", ".mov")):
            final_link_to_give = cdn_link
            display_text = "🎥 **Watch Video (Stream)**"
            
        # Baki files ke liye -> Normal Raw Link
        else:
            final_link_to_give = raw_github_link
            display_text = "🔗 **File Link**"

        # 3. User ko Link bhejo
        await status_msg.edit(
            f"✅ **Upload Complete!**\n\n"
            f"{display_text}\n"
            f"{final_link_to_give}\n\n"
            f"_(Copy karke App me use karein, ye download nahi karega)_"
        )

    except Exception as e:
        await status_msg.edit(f"❌ Error: {e}")
        
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

app.run()
