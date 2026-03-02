import os
import uuid
import logging
import asyncio
import threading
from flask import Flask, redirect
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [BOT] - %(message)s"
)
logger = logging.getLogger("Bot")

# --- FLASK SERVER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Alive"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    return redirect(f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true", code=302)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False, use_reloader=False)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- CONSTANTS ---
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
ACCESS_PASSWORD = "Maharaja Jaswant Singh"
AUTH_USERS = set()
USERBOT_ALIVE = False  # Flag to check if Userbot is running

# --- CLIENTS ---
# in_memory=True zaroori hai
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

userbot = None
if SESSION_STRING:
    userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- QUEUE LOCK ---
process_lock = asyncio.Lock()

# --- HELPER FUNCTIONS ---
async def process_media(media, message, original_msg=None):
    # 1. Size Check
    file_size = getattr(media, "file_size", 0)
    if file_size > MAX_FILE_SIZE:
        await message.reply_text("❌ **File > 500MB!**\nServer protection enabled.")
        return

    # 2. Rename Logic (Strict)
    unique_id = uuid.uuid4().hex[:6]
    m_type = str(type(media))
    
    if "Video" in m_type: final_name = f"video_{unique_id}.mp4"
    elif "Photo" in m_type: final_name = f"photo_{unique_id}.jpg"
    elif "Audio" in m_type: final_name = f"music_{unique_id}.mp3"
    else: final_name = f"pdf_{unique_id}.pdf"

    status = await message.reply_text(f"⏳ **Processing...**\n`{final_name}`")
    
    if not os.path.exists("downloads"): os.makedirs("downloads")
    local_path = f"downloads/{final_name}"

    try:
        # 3. Download
        await status.edit("⬇️ **Downloading...**")
        if original_msg:
            # Userbot download logic
            await original_msg.download(file_name=local_path)
        else:
            # Bot download logic
            await message.download(file_name=local_path)

        # 4. Upload
        await status.edit("☁️ **Uploading...**")
        api = HfApi(token=HF_TOKEN)
        
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_name,
            repo_id=HF_REPO,
            repo_type="dataset"
        )

        # 5. Reply
        link = f"{SITE_URL}/file/{final_name}"
        await status.delete()
        
        btn = InlineKeyboardButton("📂 Download Now", url=link)
        await message.reply_text(
            f"✅ **Uploaded!**\n\n🆔 `{final_name}`\n🔗 **Link:**\n`{link}`",
            reply_markup=InlineKeyboardMarkup([[btn]]),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Process Error: {e}")
        await status.edit("❌ **Failed.** Try again.")
    
    finally:
        # 6. Cleanup
        if os.path.exists(local_path): os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("👋 **Ready!**\nSend files or links.")
    else:
        await message.reply_text("🔒 **Locked.** Password required.")

@bot.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    text = message.text
    
    # Password Check
    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Unlocked!**")
        else:
            await message.reply_text("❌ **Wrong Password.**")
        return

    # Link Check
    if "t.me/" in text:
        # SAFETY CHECK ADDED HERE
        global USERBOT_ALIVE
        if not userbot or not USERBOT_ALIVE:
            return await message.reply_text("❌ **Userbot Error:** Session String expire ho gayi hai ya start nahi hui. Nayi string lagao.")

        async with process_lock:
            wait = await message.reply_text("🔎 **Searching...**")
            try:
                link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
                parts = link.split("/")
                
                if parts[0] == "c":
                    chat_id = int("-100" + parts[1])
                    msg_id = int(parts[-1].split("?")[0])
                else:
                    chat_id = parts[0]
                    msg_id = int(parts[-1].split("?")[0])

                target = await userbot.get_messages(chat_id, msg_id)
                media = target.video or target.document or target.photo or target.audio
                
                if not media:
                    await wait.edit("❌ No Media Found.")
                    return

                await wait.delete()
                await process_media(media, message, original_msg=target)
            except Exception as e:
                await wait.edit(f"❌ Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo | filters.audio)
async def file_handler(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Locked!")
    
    async with process_lock:
        media = message.video or message.document or message.photo or message.audio
        await process_media(media, message)

# --- RUNNER ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("--------------------------------")
    print("✅ Main Bot Starting...")
    await bot.start()
    
    global USERBOT_ALIVE
    if userbot:
        print("⏳ Userbot Connecting...")
        try:
            await userbot.start()
            USERBOT_ALIVE = True
            me = await userbot.get_me()
            print(f"✅ Userbot Connected: {me.first_name}")
        except Exception as e:
            USERBOT_ALIVE = False
            print(f"❌ USERBOT FAILED: {e}")
            print("⚠️ Tip: Generate NEW Session String.")
    
    print("🚀 BOT READY")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
