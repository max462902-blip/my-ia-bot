import os
import uuid
import threading
import logging
import asyncio
from flask import Flask, redirect, request
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER (Flask) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Chat Box Bot Running (No HF)"

# --- DIRECT VIEW LINK GENERATOR ---
@app.route('/view')
def view_file():
    file_id = request.args.get('id')
    if not file_id:
        return "No File ID provided", 400
    
    try:
        # Bot token use karke file path nikala jayega
        # Fir user ko Telegram server par redirect karenge
        # Note: Ye method directly Chrome me open karega
        file_obj = bot.get_file(file_id)
        file_path = file_obj.file_path
        real_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        return redirect(real_url, code=302)
    except Exception as e:
        return f"Error: Link Expired or File too big for Bot API. {e}", 404

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")

ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# --- MAIN LOGIC (NO HUGGING FACE) ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
    status = None
    local_path = None
    try:
        unique_id = uuid.uuid4().hex[:6]
        
        # --- FILENAME ---
        original_name = getattr(media, "file_name", f"file_{unique_id}")
        
        if media_type == "video":
            final_filename = f"video_{unique_id}.mp4"
        else:
            ext = os.path.splitext(original_name)[1]
            if not ext: ext = ".pdf"
            final_filename = f"document_{unique_id}{ext}"

        file_size = get_readable_size(getattr(media, "file_size", 0))

        status = await message_to_reply.reply_text(f"⏳ **Processing...**\n`{final_filename}`")

        # --- 1. DOWNLOAD (Render Local Storage) ---
        if not os.path.exists("downloads"): os.makedirs("downloads")
        local_path = f"downloads/{final_filename}"
        
        await status.edit("⬇️ **Downloading...**")
        
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # --- 2. UPLOAD TO TELEGRAM CHAT ---
        await status.edit("⬆️ **Uploading to Chat Box...**")
        
        uploaded_msg = None
        if media_type == "video":
            uploaded_msg = await message_to_reply.reply_video(
                video=local_path,
                caption="⏳ **Generating Link...**"
            )
        else:
            uploaded_msg = await message_to_reply.reply_document(
                document=local_path,
                caption="⏳ **Generating Link...**"
            )

        # --- 3. DELETE LOCAL FILE (CLEANUP) ---
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Deleted {local_path}")

        # --- 4. GENERATE LINK (Using File ID) ---
        # File ID nikalenge jo abhi upload kiya hai
        file_id = None
        if media_type == "video" and uploaded_msg.video:
            file_id = uploaded_msg.video.file_id
        elif uploaded_msg.document:
            file_id = uploaded_msg.document.file_id
        
        if not file_id:
            await status.edit("❌ Error: Could not retrieve File ID.")
            return

        # View Link banayenge
        view_link = f"{SITE_URL}/view?id={file_id}"

        # --- 5. UPDATE MESSAGE CAPTION ---
        
        # PDF LOGIC
        if media_type == "document" or final_filename.endswith(".pdf"):
            final_caption = (
                f"**Chat Box PDF**\n\n"
                f"🏷️ **Name:** `{original_name}`\n"
                f"📦 **Size:** {file_size}\n\n"
                f"🔗 **One Tap Copy Link:**\n"
                f"`{view_link}`"
            )
            await uploaded_msg.edit_caption(final_caption)
            await status.delete()

        # VIDEO LOGIC
        elif media_type == "video":
            # Video ke case me humne upar video bhej di hai
            # Ab hum uska caption edit karke link denge ya naya message?
            # User ne bola "Link dega mp4". Hum caption me hi link daal dete hain best rahega.
            
            video_caption = (
                f"🎬 **Video Ready**\n\n"
                f"🔗 **View Link (Chrome):**\n"
                f"`{view_link}`"
            )
            await uploaded_msg.edit_caption(video_caption)
            
            # Alag se bhi link bhej dete hain taaki copy easy ho
            await message_to_reply.reply_text(
                f"🎬 **Video Link:**\n`{view_link}`"
            )
            await status.delete()

    except Exception as e:
        logger.error(f"Error: {e}")
        if status: await status.edit(f"❌ Error: {e}")
        else: await message_to_reply.reply_text(f"❌ Error: {e}")
    
    finally:
        # Double check cleanup
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ **Access Granted!**")
    else:
        await message.reply_text("🔒 **Enter Password:**")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Correct!** Ab Video ya PDF bhejo.")
        else:
            await message.reply_text("❌ Wrong Password.")
        return

    # Link Handling
    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot not active.")
        
        status = await message.reply_text("🔎 **Checking Link...**")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            chat_id = int("-100" + parts[1]) if parts[0] == "c" else parts[0]
            msg_id = int(parts[-1].split("?")[0])

            target_msg = await userbot.get_messages(chat_id, msg_id)
            
            if target_msg.video:
                media = target_msg.video
                m_type = "video"
            elif target_msg.document:
                media = target_msg.document
                m_type = "document"
            else:
                await status.edit("❌ Only PDF and Video allowed.")
                return

            await status.delete()
            await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
            
        except Exception as e:
            await status.edit(f"❌ Error: {e}")

# Direct File Logic
@bot.on_message(filters.document | filters.video)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("🔒 Password bhejo pehle.")
    
    m_type = "video" if message.video else "document"
    await process_and_upload(media=message.video or message.document, message_to_reply=message, media_type=m_type)

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    if userbot: await userbot.start()
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
