import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

# बॉट सेटअप
bot = Client("my_ia_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (For Render Health & Streaming) ---
async def home(request):
    return web.Response(text="✅ Bot is Alive & Streaming Engine is Ready!", content_type="text/html")

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        range_header = request.headers.get("Range", "bytes=0-")
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        start = int(match.group(1)) if match else 0
        end = int(match.group(2)) if match and match.group(2) else file.file_size - 1
        
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file.file_size}",
            "Content-Length": str((end - start) + 1),
            "Accept-Ranges": "bytes",
        }
        response = web.StreamResponse(status=206 if request.headers.get("Range") else 200, headers=headers)
        await response.prepare(request)
        async for chunk in bot.iter_download(file.file_id, offset=start):
            await response.write(chunk)
        return response
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return web.Response(text="Error", status=500)

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nवीडियो फॉरवर्ड करें, मैं आपको **Direct Stream Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    try:
        # बॉट चैनल में कॉपी करेगा
        log_msg = await m.copy(CHANNEL_ID)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        # लिंक बनाना
        stream_link = f"{base_url}/file/{log_msg.id}?filename=video.mp4"
        await m.reply_text(f"✅ **Direct Link Ready!**\n\n🔗 `{stream_link}`")
    except Exception as e:
        await m.reply_text(f"❌ एरर: बॉट चैनल में Admin नहीं है।")

# --- MAIN RUNNER ---
async def main():
    # 1. वेब सर्वर शुरू करें (Render के लिए)
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/file/{id}", stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Server started on port {PORT}")

    # 2. बॉट शुरू करें
    await bot.start()
    logger.info("✅ BOT STARTED SUCCESSFULLY!")
    
    # 3. बॉट को चालू रखें
    await idle()
    
    # 4. सफाई
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
