import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config - YAHAN APNI VALUES DAALO
API_ID = 3598514
API_HASH = "6a0df17414daf6935f1f0a71b8af1ee0"
BOT_TOKEN = "8546752495:AAEOiZypE6VhSvOG7JOd9n4GYpCioUTsNQw"
CHANNEL_ID = -1003800002652  # Yeh sahi hai?
PORT = 10000
BASE_URL = "https://my-ia-bot-la0g.onrender.com"

# Bot start
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB HANDLER ---
async def home(request):
    return web.Response(text="Bot is running! Send video to @Filesheringmp4bot", content_type="text/html")

async def stream(request):
    return web.Response(text="Stream handler working", content_type="text/html")

# --- BOT HANDLERS - YAHAN SE REPLY AAYEGA ---
@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text("✅ **Bot is Working!**\n\nSend me any video and I'll give you stream link.")

@bot.on_message(filters.command("help"))
async def help_handler(client, message):
    await message.reply_text("Just send me a video file.")

@bot.on_message(filters.video | filters.document)
async def video_handler(client, message):
    try:
        await message.reply_text("⏳ Processing your video...")
        
        # Channel me forward karo
        msg = await message.copy(CHANNEL_ID)
        
        # Link banao
        link = f"{BASE_URL}/stream/{msg.id}"
        
        # Reply bhejo
        await message.reply_text(f"✅ **Stream Link Ready!**\n\n{link}")
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# --- MAIN FUNCTION ---
async def main():
    # Web server
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/stream/{id}", stream)
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    # Bot start
    await bot.start()
    logger.info("Bot started!")
    
    # Bot info
    me = await bot.get_me()
    logger.info(f"Bot: @{me.username}")
    
    # Keep running
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
