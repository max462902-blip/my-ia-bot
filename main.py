import os
import asyncio
import logging
from pyrogram import Client, filters
from aiohttp import web

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config - EK BAAR SET KARO, FIR MAT BADLO
API_ID = 3598514
API_HASH = "6a0df17414daf6935f1f0a71b8af1ee0"
BOT_TOKEN = "8546752495:AAEOiZypE6VhSvOG7JOd9n4GYpCioUTsNQw"  # Ye final token hai
CHANNEL_ID = -1003800002652
PORT = int(os.environ.get("PORT", 10000))
BASE_URL = "https://my-ia-bot-la0g.onrender.com"  # Tera Render URL

# Bot
bot = Client(
    "my_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN
)

# --- WEBHOOK HANDLER ---
async def webhook_handler(request):
    """Telegram se webhook requests yahan aayengi"""
    try:
        # Request ko process karo
        update_data = await request.json()
        logger.info(f"Received update: {update_data}")
        
        # Update ko bot mein feed karo
        await bot.process_update(update_data)
        
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

async def home(request):
    return web.Response(text="Bot is running with webhook! Send video to @Filesheringmp4bot")

async def health(request):
    """Render ke health check ke liye"""
    return web.Response(text="OK")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    logger.info(f"Start from {message.from_user.id}")
    await message.reply_text(
        "✅ **Bot is Working!**\n\n"
        "Send me any video and I'll give you stream link."
    )

@bot.on_message(filters.video | filters.document)
async def video_handler(client, message):
    try:
        logger.info(f"Video from {message.from_user.id}")
        await message.reply_text("⏳ Processing...")
        
        # Channel me forward
        forwarded = await message.copy(CHANNEL_ID)
        stream_link = f"{BASE_URL}/stream/{forwarded.id}"
        
        await message.reply_text(
            f"✅ **Stream Link Ready!**\n\n"
            f"🔗 `{stream_link}`\n\n"
            f"Open in browser"
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

# --- STREAM HANDLER (for video streaming) ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        
        range_header = request.headers.get("Range", "bytes=0-")
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        start = int(match.group(1)) if match else 0
        end = int(match.group(2)) if match and match.group(2) else file_size - 1
        
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1),
            "Accept-Ranges": "bytes",
        }
        
        response = web.StreamResponse(status=206 if range_header != "bytes=0-" else 200, headers=headers)
        await response.prepare(request)
        
        # Stream file
        async for chunk in bot.stream_media(msg, limit=1024*1024):
            await response.write(chunk)
            
        return response
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return web.Response(status=500)

# --- MAIN ---
async def main():
    # Webhook URL setup
    webhook_url = f"{BASE_URL}/webhook"
    
    # Delete old webhook and set new one
    await bot.start()
    
    # Delete any existing webhook
    await bot.delete_webhook()
    logger.info("Old webhook deleted")
    
    # Set new webhook
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")
    
    # Bot info
    me = await bot.get_me()
    logger.info(f"Bot: @{me.username}")
    
    # Web server setup
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)  # Webhook endpoint
    app.router.add_get("/", home)
    app.router.add_get("/health", health)  # Health check for Render
    app.router.add_get("/stream/{id}", stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Server running on port {PORT}")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
