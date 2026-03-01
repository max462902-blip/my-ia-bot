import os
import logging
import asyncio
from flask import Flask
from pyrogram import Client, filters
from dotenv import load_dotenv

# Simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env
load_dotenv()

# Flask app for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Config
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_REPO = os.getenv("HF_REPO", "")

# Password
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# Simple bot
bot = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Basic handlers
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    logger.info(f"Start command from {message.from_user.id}")
    await message.reply_text("Bot is working! Send /ping to test.")

@bot.on_message(filters.command("ping"))
async def ping_command(client, message):
    logger.info(f"Ping command from {message.from_user.id}")
    await message.reply_text("Pong! 🏓")

@bot.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    text = message.text
    
    logger.info(f"Message from {user_id}: {text}")
    
    # Authentication
    if user_id not in AUTH_USERS:
        if text == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("✅ Access granted!")
            logger.info(f"User {user_id} authenticated")
        else:
            await message.reply_text("❌ Wrong password")
        return
    
    # Echo for testing
    await message.reply_text(f"You said: {text}")

@bot.on_message(filters.photo)
async def photo_handler(client, message):
    logger.info(f"Photo from {message.from_user.id}")
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("Not authorized")
    await message.reply_text("Photo received!")

@bot.on_message(filters.video)
async def video_handler(client, message):
    logger.info(f"Video from {message.from_user.id}")
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("Not authorized")
    await message.reply_text("Video received!")

@bot.on_message(filters.document)
async def document_handler(client, message):
    logger.info(f"Document from {message.from_user.id}")
    if message.from_user.id not in AUTH_USERS:
        return await message.reply_text("Not authorized")
    await message.reply_text("Document received!")

async def main():
    try:
        # Start Flask in thread
        import threading
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask started on port " + os.environ.get("PORT", "8080"))
        
        # Start bot
        logger.info("Starting bot...")
        await bot.start()
        
        # Get bot info
        me = await bot.get_me()
        logger.info(f"Bot started: @{me.username}")
        
        # Send test message to yourself
        try:
            await bot.send_message(5414986061, "✅ Bot started successfully!")
            logger.info("Test message sent to admin")
        except:
            logger.warning("Could not send test message to admin")
        
        logger.info("Bot is running. Waiting for messages...")
        
        # Keep running
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
