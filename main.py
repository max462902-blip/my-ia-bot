import os
import uuid
import threading
import logging
import asyncio
import time
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): 
    return "All-Rounder Bot is Running! ✓"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    if not hf_repo:
        return "HF_REPO not configured", 500
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Run Flask in a separate thread"""
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- CONFIG ---
try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    HF_TOKEN = os.getenv("HF_TOKEN")
    HF_REPO = os.getenv("HF_REPO")
    SESSION_STRING = os.getenv("SESSION_STRING")
    
    # Validate required variables
    if not all([API_ID, API_HASH, BOT_TOKEN, HF_TOKEN, HF_REPO]):
        raise ValueError("Missing required environment variables")
        
    logger.info("Configuration loaded successfully")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- CLIENTS ---
bot = Client(
    "main_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    workers=4,
    sleep_threshold=60
)

userbot = None
if SESSION_STRING:
    userbot = Client(
        "user_bot", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        session_string=SESSION_STRING,
        workers=4,
        sleep_threshold=60
    )
    logger.info("Userbot configured")
else:
    logger.warning("SESSION_STRING not provided - userbot features disabled")

def get_readable_size(size):
    try:
        size = int(size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: 
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    except:
        return "Unknown"

# --- MAIN UPLOAD FUNCTION ---
async def process_and_upload(media, message_to_reply, original_msg=None, media_type=None):
    status = None
    local_path = None
    
    try:
        unique_id = uuid.uuid4().hex[:6]
        
        # --- NAME & TYPE DETECTION ---
        if media_type == "photo":
            final_filename = f"image_{unique_id}.jpg"
            file_type_msg = "🖼️ Image"
        elif media_type == "video":
            final_filename = f"video_{unique_id}.mp4"
            file_type_msg = "🎬 Video"
        elif media_type == "document":
            # Try to preserve original filename for documents
            if hasattr(media, 'file_name') and media.file_name:
                name, ext = os.path.splitext(media.file_name)
                final_filename = f"{name}_{unique_id}{ext}"
            else:
                final_filename = f"document_{unique_id}.bin"
            file_type_msg = "📄 Document"
        else:
            final_filename = f"file_{unique_id}.bin"
            file_type_msg = "📎 File"
        
        file_size = get_readable_size(getattr(media, "file_size", 0))

        status = await message_to_reply.reply_text(f"⏳ **Processing...**\n`{final_filename}`")

        # Download Path
        download_dir = "downloads"
        if not os.path.exists(download_dir): 
            os.makedirs(download_dir)
            
        local_path = os.path.join(download_dir, final_filename)
        
        await status.edit("⬇️ **Downloading...**")
        
        # Download
        if original_msg:
            await original_msg.download(file_name=local_path)
        else:
            await message_to_reply.download(file_name=local_path)

        # Verify download
        if not os.path.exists(local_path):
            raise Exception("Download failed - file not found")
        
        file_size_actual = os.path.getsize(local_path)
        logger.info(f"Downloaded {final_filename} - Size: {file_size_actual} bytes")

        # Upload
        await status.edit("⬆️ **Uploading to HuggingFace...**")
        api = HfApi(token=HF_TOKEN)
        
        # Upload in thread to avoid blocking
        await asyncio.to_thread(
            api.upload_file,
            path_or_fileobj=local_path,
            path_in_repo=final_filename,
            repo_id=HF_REPO,
            repo_type="dataset"
        )
        
        logger.info(f"Uploaded {final_filename} to HuggingFace")

        branded_link = f"{SITE_URL}/file/{final_filename}"
        
        # Create appropriate button
        if media_type == "video":
            btn = InlineKeyboardButton("🎬 Play Video", url=branded_link)
        elif media_type == "photo":
            btn = InlineKeyboardButton("🖼️ View Image", url=branded_link)
        else:
            btn = InlineKeyboardButton("📥 Download", url=branded_link)

        msg = (
            f"✅ **{file_type_msg} Saved!**\n\n"
            f"🔗 **Link:**\n`{branded_link}`\n\n"
            f"📦 **Size:** {file_size}\n\n"
            f"💾 **Actual Size:** {get_readable_size(file_size_actual)}"
        )

        await status.delete()
        await message_to_reply.reply_text(
            msg, 
            reply_markup=InlineKeyboardMarkup([[btn]]),
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        if status:
            await status.edit(f"❌ Error: {str(e)}")
        else:
            await message_to_reply.reply_text(f"❌ Error: {str(e)}")
    
    finally:
        # Cleanup
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.info(f"Cleaned up {local_path}")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    logger.info(f"Start command from user {user_id}")
    
    if user_id in AUTH_USERS:
        await message.reply_text(
            "✅ **Access Granted!**\n\n"
            "Send me:\n"
            "• Photos 📸\n"
            "• Videos 🎬\n"
            "• Documents 📄\n"
            "• Telegram message links 🔗\n\n"
            "I'll upload them to HuggingFace and give you a direct link!"
        )
    else:
        await message.reply_text(
            "🔒 **Bot Locked!**\n\n"
            "Please enter the access password to unlock."
        )

@bot.on_message(filters.command("stats"))
async def stats(client, message):
    if message.from_user.id not in AUTH_USERS:
        return
    
    stats_msg = (
        f"**Bot Statistics**\n\n"
        f"• Authorized Users: {len(AUTH_USERS)}\n"
        f"• Userbot Active: {'✓' if userbot else '✗'}\n"
        f"• HF Repo: `{HF_REPO}`\n"
        f"• Flask URL: {SITE_URL}"
    )
    await message.reply_text(stats_msg)

@bot.on_message(filters.command("broadcast") & filters.user(5414986061))  # Your ID
async def broadcast(client, message):
    """Broadcast message to all authorized users"""
    if len(AUTH_USERS) == 0:
        return await message.reply_text("No authorized users")
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: /broadcast <message>")
    
    broadcast_text = message.text.split(None, 1)[1]
    success = 0
    failed = 0
    
    status = await message.reply_text("Broadcasting...")
    
    for user_id in AUTH_USERS:
        try:
            await client.send_message(user_id, f"📢 **Broadcast**\n\n{broadcast_text}")
            success += 1
            await asyncio.sleep(0.3)  # Avoid flood
        except:
            failed += 1
    
    await status.edit(f"Broadcast complete!\n✓ Success: {success}\n✗ Failed: {failed}")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    logger.info(f"Text message from {user_id}: {text[:50]}...")

    # Authentication check
    if user_id not in AUTH_USERS:
        if text == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text(
                "🔓 **Bot Unlocked!**\n\n"
                "Access granted! Now you can:\n"
                "• Send photos/videos/documents\n"
                "• Send Telegram message links\n"
                "• Get direct download links"
            )
            logger.info(f"User {user_id} authenticated")
        else:
            await message.reply_text("❌ Wrong password. Access denied.")
        return

    # Handle Telegram links
    if any(x in text for x in ["t.me/", "telegram.me/"]):
        if not userbot:
            return await message.reply_text("❌ Userbot not configured. Cannot fetch from links.")
        
        wait_msg = await message.reply_text("🕵️ **Fetching content from Telegram...**")
        
        try:
            # Parse Telegram link
            # Remove protocol and domain
            clean_link = text.replace("https://", "").replace("http://", "").replace("www.", "")
            clean_link = clean_link.replace("t.me/", "").replace("telegram.me/", "")
            
            # Split parts
            parts = clean_link.split("/")
            logger.info(f"Parsed link parts: {parts}")
            
            # Handle different link formats
            if len(parts) >= 2:
                # Check if it's a private channel link (c/)
                if parts[0] == "c":
                    chat_id = int("-100" + parts[1])
                    msg_id_index = 2
                else:
                    chat_id = parts[0]
                    msg_id_index = 1
                
                # Get message ID (remove query parameters)
                if len(parts) > msg_id_index:
                    msg_id_part = parts[msg_id_index].split("?")[0]
                    msg_id = int(msg_id_part)
                else:
                    return await message.reply_text("❌ Invalid link format. Include message ID.")
                
                # Fetch message
                await wait_msg.edit("📥 **Fetching message...**")
                target_msg = await userbot.get_messages(chat_id, msg_id)
                
                if not target_msg:
                    return await message.reply_text("❌ Message not found or inaccessible.")
                
                # Detect media type
                if target_msg.photo:
                    media = target_msg.photo
                    m_type = "photo"
                    media_name = "photo"
                elif target_msg.video:
                    media = target_msg.video
                    m_type = "video"
                    media_name = "video"
                elif target_msg.document:
                    media = target_msg.document
                    m_type = "document"
                    media_name = "document"
                elif target_msg.audio:
                    media = target_msg.audio
                    m_type = "document"
                    media_name = "audio"
                else:
                    await wait_msg.delete()
                    return await message.reply_text("❌ No media found in that message.")
                
                await wait_msg.delete()
                await process_and_upload(media, message, original_msg=target_msg, media_type=m_type)
            else:
                await message.reply_text("❌ Invalid link format.")
                
        except Exception as e:
            logger.error(f"Link processing error: {e}", exc_info=True)
            await message.reply_text(f"❌ Error: {str(e)}\n\nMake sure the userbot has access to this channel/message.")
    else:
        await message.reply_text("Send me a file, photo, video, or Telegram link!")

# DIRECT FILE HANDLER
@bot.on_message(filters.photo | filters.video | filters.document | filters.audio)
async def handle_file(client, message):
    user_id = message.from_user.id
    logger.info(f"File from user {user_id}")
    
    if user_id not in AUTH_USERS:
        return await message.reply_text("🔒 Bot is locked! Send the access password first.")
    
    if message.photo:
        media = message.photo
        m_type = "photo"
    elif message.video:
        media = message.video
        m_type = "video"
    elif message.audio:
        media = message.audio
        m_type = "document"
    else:  # document
        media = message.document
        m_type = "document"
    
    await process_and_upload(media, message, media_type=m_type)

@bot.on_message(filters.command("users"))
async def list_users(client, message):
    """List all authorized users (admin only)"""
    if message.from_user.id != 5414986061:  # Your ID
        return
    
    if AUTH_USERS:
        users_list = "\n".join([f"• `{uid}`" for uid in AUTH_USERS])
        await message.reply_text(f"**Authorized Users ({len(AUTH_USERS)}):**\n\n{users_list}")
    else:
        await message.reply_text("No authorized users.")

async def main():
    """Main function to start all services"""
    try:
        # Start Flask in thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask thread started")
        
        # Start bot
        logger.info("Starting bot...")
        await bot.start()
        logger.info("Bot started successfully!")
        
        # Get bot info
        bot_info = await bot.get_me()
        logger.info(f"Bot username: @{bot_info.username}")
        
        # Start userbot if available
        if userbot:
            logger.info("Starting userbot...")
            await userbot.start()
            logger.info("Userbot started successfully!")
            
            # Check userbot status
            try:
                me = await userbot.get_me()
                logger.info(f"Userbot: @{me.username or me.first_name}")
            except:
                logger.warning("Could not get userbot info")
        
        # Send startup message to admin
        try:
            await bot.send_message(
                5414986061,  # Your ID
                f"✅ **Bot Started!**\n\n"
                f"• Bot: @{bot_info.username}\n"
                f"• Userbot: {'Active' if userbot else 'Inactive'}\n"
                f"• Flask URL: {SITE_URL}"
            )
        except:
            pass
        
        logger.info("Bot is now idle. Listening for messages...")
        await idle()
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise
    finally:
        logger.info("Stopping bot...")
        await bot.stop()
        if userbot:
            await userbot.stop()
        logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        # Run with proper asyncio handling
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
