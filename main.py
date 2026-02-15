import os
import asyncio
import logging
import re
from pyrogram import Client, filters
from aiohttp import web

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== YAHAN APNI VALUES DAALO ==========
API_ID = 35985614  # 🔴 YAHAN NAYA API_ID DAALO jo my.telegram.org se mila
API_HASH = "6a0df17414daf6935f1f0a71b8af1ee9"  # 🔴 YAHAN NAYA API_HASH DAALO
BOT_TOKEN = "8546752495:AAEOiZypE6VhSvOG7JOd9n4GYpCioUTsNQw"  # Bot token
CHANNEL_ID = -1003800002652  # Channel ID
PORT = 10000
BASE_URL = "https://my-ia-bot-la0g.onrender.com"
# =============================================

# Bot
bot = Client(
    "my_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN
)

# --- Handlers ---
@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text("✅ **Bot Working!** Send me a video.")

@bot.on_message(filters.video | filters.document)
async def video_handler(client, message):
    try:
        await message.reply_text("⏳ Processing...")
        forwarded = await message.copy(CHANNEL_ID)
        stream_link = f"{BASE_URL}/stream/{forwarded.id}"
        await message.reply_text(f"✅ **Stream Link:**\n\n`{stream_link}`")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# --- Stream Handler ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        file = msg.video or msg.document
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Length": str(file.file_size),
        }
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        async for chunk in bot.stream_media(msg):
            await response.write(chunk)
        return response
    except Exception as e:
        return web.Response(text=str(e), status=500)

async def home(request):
    return web.Response(text="Bot Running!")

# --- Webhook Handler ---
async def webhook_handler(request):
    update = await request.json()
    await bot.process_update(update)
    return web.Response(text="OK")

# --- Main ---
async def main():
    # Webhook setup
    await bot.start()
    await bot.delete_webhook()
    await bot.set_webhook(f"{BASE_URL}/webhook")
    logger.info("Webhook set!")
    
    # Web server
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/", home)
    app.router.add_get("/stream/{id}", stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Server running on port {PORT}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
