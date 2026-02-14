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

bot = Client("link_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- RANGE PARSER ---
def parse_range(range_str, size):
    if not range_str:
        return 0, size - 1
    match = re.match(r'bytes=(\d+)-(\d*)', range_str)
    if not match:
        return 0, size - 1
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else size - 1
    return start, end

# --- STREAMING HANDLER (With Range Support) ---
async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        range_header = request.headers.get("Range")
        
        start, end = parse_range(range_header, file_size)
        content_length = (end - start) + 1

        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await response.prepare(request)

        # Telegram से डेटा को Offset (बाइट्स) के साथ डाउनलोड करना
        async for chunk in bot.iter_download(file.file_id, offset=start):
            await response.write(chunk)
            
        return response
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        return web.Response(text="Internal Error", status=500)

async def home_handler(request):
    return web.Response(text="✅ Streaming Engine is Active with Range Support!", content_type="text/html")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nवीडियो भेजें, मैं **High-Speed Direct Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    try:
        sent_msg = await m.reply_text("⏳ लिंक बन रहा है, कृपया प्रतीक्षा करें...", quote=True)
        log_msg = await m.copy(CHANNEL_ID)
        
        # Render URL Setup
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{log_msg.id}"
        
        await sent_msg.edit_text(f"✅ **Video Ready!**\n\n🔗 `{stream_link}`\n\nइसे अपने ऐप में यूज़ करें।")
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}")

# --- STARTUP ---
async def start_services():
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await bot.start()
    logger.info("✅ BOT STARTED WITH RANGE SUPPORT")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_services())
