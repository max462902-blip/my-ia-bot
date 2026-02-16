import os
import uuid
import threading
import logging
import asyncio
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- SERVER KEEPER (Bot ko sone nahi dega) ---
app = Flask(__name__)
@app.route('/')
def home(): return "HuggingFace Permanent Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- CONFIG ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO") # Value: Jitendra55566/my-storage

bot = Client("hf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=2)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("✅ **Permanent Storage Bot Ready!**\nFile bhejo, main Life-Time Link dunga.")

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    try:
        media = message.video or message.document
        if not media: return

        # 1. File Name Safai
        if message.video:
            # Video ka naam nahi hota forward mein, isliye khud banayenge
            original_name = f"video_{uuid.uuid4().hex[:5]}.mp4"
        else:
            original_name = media.file_name or f"file_{uuid.uuid4().hex[:5]}.pdf"
        
        # Spaces hatana zaroori hai link ke liye
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        file_size = get_readable_size(media.file_size)

        status = await message.reply_text(f"⏳ **Processing...**\n`{safe_name}`")

        # 2. Download
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{safe_name}"
        
        await status.edit("⬇️ **Downloading...**")
        await message.download(file_name=local_path)

        # 3. Upload to Hugging Face
        await status.edit("⬆️ **Uploading to Permanent Cloud...**")
        
        api = HfApi(token=HF_TOKEN)
        
        # Background mein upload taaki bot ruke nahi
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=safe_name,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 4. Link Generate (Magic Link jo Chrome me chalega)
        # Format: https://huggingface.co/datasets/USER/REPO/resolve/main/FILE
        direct_link = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{safe_name}"
        
        # 5. Success Reply
        if message.video:
            msg = f"✅ **Video Saved Forever!**\n\n🔗 **Direct Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("🎬 Play Video", url=direct_link)
        else:
            msg = f"✅ **PDF Saved Forever!**\n\n🔗 **Direct Link:**\n`{direct_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("📄 Open PDF", url=direct_link)

        await status.delete()
        await message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))

    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup (Server khali karna)
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
