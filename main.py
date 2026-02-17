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

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Secure Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
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

# --- SECURITY CONFIG (Yahan Password Set Hai) ---
ACCESS_PASSWORD = "kp_2324"
# Ye list yaad rakhegi ki kisne sahi password diya hai
AUTH_USERS = set()

bot = Client("hf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=2)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

# --- COMMANDS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    
    # Check agar user pehle se login hai
    if user_id in AUTH_USERS:
        await message.reply_text(
            "✅ **Access Granted!**\n\n"
            "Aap login hain. PDF ya Video bhejo, main link bana dunga.\n"
            "(Admin: @Kaal_Shadow)"
        )
    else:
        await message.reply_text(
            "🔒 **Bot Locked!**\n\n"
            "Is bot ko use karne ke liye **Access ID** ki zaroorat hai.\n"
            "Kripya niche **Access ID** likh kar bhejein."
        )

# --- PASSWORD CHECKER ---
@bot.on_message(filters.text & filters.private)
async def check_password(client, message):
    user_id = message.from_user.id
    
    # Agar user pehle se authorized hai, to text ignore karo (ya chat karo)
    if user_id in AUTH_USERS:
        return 

    # Password Check
    if message.text.strip() == ACCESS_PASSWORD:
        AUTH_USERS.add(user_id)
        await message.reply_text(
            "🔓 **Access Unlocked!**\n\n"
            "Password sahi hai. Ab aap Files bhej sakte hain."
        )
    else:
        await message.reply_text("❌ **Galat Access ID!**\nSahi ID bhejein ya Admin se contact karein.")

# --- FILE HANDLER ---
@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    # --- SECURITY CHECK ---
    # Agar user list mein nahi hai, to file reject karo
    if message.from_user.id not in AUTH_USERS:
        await message.reply_text("⛔ **Permission Denied!**\n\nPehle `/start` dabayein aur sahi **Access ID** bhejein.")
        return
    # ----------------------

    try:
        media = message.video or message.document
        if not media: return

        # 1. File Name Logic
        if message.video:
            original_name = f"video_{uuid.uuid4().hex[:5]}.mp4"
        else:
            original_name = media.file_name or f"file_{uuid.uuid4().hex[:5]}.pdf"
        
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        file_size = get_readable_size(media.file_size)

        status = await message.reply_text(f"⏳ **Processing...**\n`{safe_name}`")

        # 2. Download
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{safe_name}"
        
        await status.edit("⬇️ **Downloading...**")
        await message.download(file_name=local_path)

        # 3. Upload
        await status.edit("⬆️ **Uploading...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=safe_name,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        branded_link = f"{SITE_URL}/file/{safe_name}"
        
        # 4. Success Reply
        if message.video:
            msg = f"✅ **Video Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("🎬 Play Video", url=branded_link)
        else:
            msg = f"✅ **PDF Link:**\n`{branded_link}`\n\n📦 **Size:** {file_size}"
            btn = InlineKeyboardButton("📄 Open PDF", url=branded_link)

        await status.delete()
        await message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[btn]]))

    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")
    
    finally:
        if os.path.exists(local_path): os.remove(local_path)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
