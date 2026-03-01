import os
import uuid
import logging
import asyncio
import threading
from flask import Flask, redirect
from pyrogram import Client, filters
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
print("✅ Bot Starting...")

# --- FLASK SERVER (Render ke liye) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Simple Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    # Redirect to HuggingFace
    return redirect(f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true", code=302)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)

# --- BOT CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")

# --- CLIENT (No Session File) ---
# in_memory=True rakha hai taaki ye purana bot na pakde
bot = Client("simple_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- QUEUE LOCK ---
# Ye ensure karega ki ek file upload hone ke baad hi dusri start ho
upload_lock = asyncio.Lock()

# --- START COMMAND ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Bot Connected!**\nSend Video or PDF to upload.")

# --- FILE HANDLER ---
@bot.on_message(filters.video | filters.document)
async def handle_file(client, message):
    # Queue System: Wait karo agar koi file upload ho rahi hai
    async with upload_lock:
        status_msg = await message.reply_text("⏳ **Added to Queue...**")
        
        try:
            # 1. File Name Generate
            unique_id = uuid.uuid4().hex[:6]
            if message.video:
                filename = f"video_{unique_id}.mp4"
            else:
                filename = f"pdf_{unique_id}.pdf"
            
            # 2. Download
            await status_msg.edit(f"⬇️ **Downloading...**\n`{filename}`")
            path = await message.download(file_name=filename)
            
            # 3. Upload to HuggingFace
            await status_msg.edit("⬆️ **Uploading to Cloud...**")
            api = HfApi(token=HF_TOKEN)
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=path,
                path_in_repo=filename,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            # 4. Cleanup Local File
            if os.path.exists(path):
                os.remove(path)

            # 5. Generate Link
            final_link = f"{SITE_URL}/file/{filename}"

            # 6. Reply (One Click Copy)
            await status_msg.delete()
            await message.reply_text(
                f"✅ **Uploaded Successfully!**\n\n📂 **File:** `{filename}`\n🔗 **Link:**\n`{final_link}`",
                disable_web_page_preview=True
            )

        except Exception as e:
            print(f"Error: {e}")
            await status_msg.edit(f"❌ Error: {e}")
            # Error aane par bhi file delete karo
            if 'path' in locals() and os.path.exists(path):
                os.remove(path)

# --- RUNNER ---
if __name__ == "__main__":
    # Flask alag thread me chalega
    threading.Thread(target=run_flask, daemon=True).start()
    # Bot start
    bot.run()
