import os
import uuid
import threading
import logging
import asyncio
from flask import Flask, redirect
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- SERVER KEEPER & LINK MASKER ---
app = Flask(__name__)

# Render ka URL automatic uthana (Agar na mile to localhost)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): 
    return "Bot is Running Live!"

# --- JADU (Magic) Route ---
# Ye function HuggingFace ke link ko chupata hai
@app.route('/file/<path:filename>')
def file_redirect(filename):
    # Asli file yahan hai
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    
    # User ko wahan bhej do (Redirect)
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO") 

bot = Client("hf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=2)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Branded Bot Ready!**\nPDF ya video bhejo, opn Link main convert krke de dunga (Teligram id - @Kaal_Shadow ).")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    try:
        media = message.video or message.document
        if not media: return

        # 1. File Name Safai
        if message.video:
            # Video ke liye extension mp4 fix rakhenge
            original_name = f"video_{uuid.uuid4().hex[:5]}.mp4"
        else:
            # PDF ke liye original naam ya random
            original_name = media.file_name or f"file_{uuid.uuid4().hex[:5]}.pdf"
        
        # Spaces aur brackets hatana (URL ke liye zaroori)
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        file_size = get_readable_size(media.file_size)

        status = await message.reply_text(f"⏳ **Processing...**\n`{safe_name}`")

        # 2. Download
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{safe_name}"
        
        await status.edit("⬇️ **Downloading...**")
        await message.download(file_name=local_path)

        # 3. Upload to Hugging Face
        await status.edit("⬆️ **Uploading to Cloud...**")
        api = HfApi(token=HF_TOKEN)
        
        # Background Upload
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=safe_name,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 4. Branded Link Generate Karna
        # Ab hum HuggingFace ka link nahi denge, balki apna Render wala link denge
        branded_link = f"{SITE_URL}/file/{safe_name}"
        
        # 5. Reply Message
        if message.video:
            msg = f"✅ **Video Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("🎬 Play Video", url=branded_link)
        else:
            msg = f"✅ **PDF Saved!**\n\n🔗 **Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("📄 Open PDF", url=branded_link)

        await status.delete()
        await message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))

    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup (Local file delete)
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
