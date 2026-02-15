import os
import asyncio
import logging
import re
import urllib.parse
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://my-ia-bot-la0g.onrender.com").rstrip('/')

# Bot initialization
bot = Client("proxy_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- STREAM HANDLER ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        
        range_header = request.headers.get("Range", "bytes=0-")
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        start = int(match.group(1)) if match else 0
        end = int(match.group(2)) if match and match.group(2) else file_size - 1
        
        chunk_size = (end - start) + 1
        mime_type = file.mime_type or "video/mp4"
        
        headers = {
            "Content-Type": mime_type,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=206 if request.headers.get("Range") else 200, headers=headers)
        await response.prepare(request)

        # Download and stream
        downloaded = 0
        current = start
        
        async for chunk in bot.stream_media(msg):
            chunk_len = len(chunk)
            if current + chunk_len <= start:
                current += chunk_len
                continue
            
            chunk_start = max(0, start - current)
            chunk_end = min(chunk_len, end - current + 1)
            
            if chunk_start < chunk_end:
                await response.write(chunk[chunk_start:chunk_end])
                downloaded += (chunk_end - chunk_start)
            
            current += chunk_len
            if downloaded >= chunk_size:
                break
                
        return response
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return web.Response(text="Error occurred", status=500)

# --- HOME PAGE ---
async def home(request):
    return web.Response(text="✅ Bot is Running! Send video to @Filesheringmp4bot", content_type="text/html")

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text("✅ **Bot is Working!**\n\nSend me any video and I'll give you a direct stream link.")

@bot.on_message(filters.command("restart") & filters.private)
async def restart_command(client, message):
    await message.reply_text("🔄 Bot is running fine!")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_media(client, message):
    try:
        status = await message.reply_text("⏳ Processing...")
        
        # Forward to channel
        forwarded = await message.copy(CHANNEL_ID)
        
        # Generate link
        stream_link = f"{BASE_URL}/stream/{forwarded.id}"
        
        # Get file name
        if message.video:
            file_name = message.video.file_name or "video.mp4"
        else:
            file_name = message.document.file_name or "file.mp4"
        
        await status.delete()
        await message.reply_text(
            f"✅ **Stream Link Generated!**\n\n"
            f"📁 `{file_name}`\n"
            f"🔗 `{stream_link}`\n\n"
            f"Open in browser or VLC Player"
        )
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# --- MAIN FUNCTION ---
async def main():
    # Web app
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/stream/{id}", stream_handler)
    
    # Web server
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Web server running on port {PORT}")
    
    # Bot start
    await bot.start()
    logger.info("🤖 Bot started!")
    
    me = await bot.get_me()
    logger.info(f"Bot username: @{me.username}")
    logger.info(f"Base URL: {BASE_URL}")
    
    await idle()
    
    await bot.stop()
    await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
