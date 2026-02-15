import os
import asyncio
import logging
import re
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

bot = Client("proxy_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- STREAMING ENGINE (The Core) ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        # टेलीग्राम चैनल से मैसेज निकालें
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found in channel!", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        
        # Range Header (Chrome/App की मांग)
        range_header = request.headers.get("Range", "bytes=0-")
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        start = int(match.group(1)) if match else 0
        end = int(match.group(2)) if match and match.group(2) else file_size - 1
        
        chunk_size = (end - start) + 1
        
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=206 if request.headers.get("Range") else 200, headers=headers)
        await response.prepare(request)

        # टेलीग्राम से सीधा डेटा स्ट्रीम करना (No disk storage)
        async for chunk in bot.iter_download(file.file_id, offset=start):
            await response.write(chunk)
            
        return response
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return web.Response(text="Error occurred", status=500)

async def home(request):
    return web.Response(text="✅ Direct Proxy Stream Engine is Running!", content_type="text/html")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे वीडियो भेजें, मैं आपको **Direct Stream Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    try:
        log_msg = await m.copy(CHANNEL_ID)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{log_msg.id}?filename=video.mp4"
        await m.reply_text(f"✅ **Direct Link Ready!**\n\n🔗 `{stream_link}`\n\nइसे अपने एडमिन पैनल में लगायें।")
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}")

# --- STARTUP ---
async def main():
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/file/{id}", stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await bot.start()
    logger.info("✅ BOT STARTED")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
