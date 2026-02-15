import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# 1. Logging Setup (ताकि हम रेंडर पर सब देख सकें)
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. Configuration
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

# बॉट क्लाइंट
bot = Client("my_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER LOGIC (Render के लिए) ---
async def home_handler(request):
    return web.Response(text="✅ बॉट ऑनलाइन है और रिप्लाई देने के लिए तैयार है!", content_type="text/html")

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="फाइल नहीं मिली!", status=404)
        
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
        logger.error(f"Streaming Error: {e}")
        return web.Response(text="Error", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    logger.info(f"Start command received from {m.from_user.id}")
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nबॉट चालू है। मुझे कोई भी वीडियो फॉरवर्ड करें, मैं आपको उसका **Direct MP4 Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    try:
        sent_msg = await m.reply_text("⏳ लिंक बन रहा है, कृपया प्रतीक्षा करें...", quote=True)
        log_msg = await m.copy(CHANNEL_ID)
        
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{log_msg.id}?filename=video.mp4"
        
        await sent_msg.edit_text(f"✅ **लिंक तैयार है!**\n\n🔗 `{stream_link}`\n\nइसे अपने एडमिन पैनल में लगायें।")
    except Exception as e:
        logger.error(f"Copy Error: {e}")
        await m.reply_text("❌ एरर: बॉट चैनल में Admin नहीं है।")

# --- MAIN RUNNER ---
async def main():
    # वेब सर्वर शुरू करें
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web Server started on port {PORT}")

    # बॉट शुरू करें
    await bot.start()
    logger.info("✅ बॉट सफलतापूर्वक शुरू हो गया है!")
    
    await idle() # बॉट को रिप्लाई सुनने के लिए चालू रखें

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
