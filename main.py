import os
import logging
import asyncio
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("link_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ADVANCED STREAMING HANDLER ---
async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found in channel!", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        mime_type = file.mime_type or "video/mp4"

        # प्लेयर को बताने के लिए जरूरी Headers
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{getattr(file, "file_name", "video.mp4")}"'
        }

        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)

        # फाइल को टुकड़ों में भेजना (Streaming)
        async for chunk in bot.iter_download(file.file_id):
            await response.write(chunk)
            
        return response

    except Exception as e:
        logger.error(f"Streaming Error: {e}")
        return web.Response(text="Internal Server Error", status=500)

async def home_handler(request):
    return web.Response(text="✅ Streaming Engine is Active!", content_type="text/html")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\nवीडियो भेजें, मैं Direct MP4 लिंक दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_forward(c, m):
    try:
        # चैनल में कॉपी करें
        log_msg = await m.copy(CHANNEL_ID)
        # Render URL को सही से क्लीन करें
        raw_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        base_url = raw_url.rstrip('/')
        
        stream_link = f"{base_url}/file/{log_msg.id}"
        await m.reply_text(f"✅ **Video Ready to Stream!**\n\n🔗 `{stream_link}`\n\nइसे अपने ऐप में लगायें।")
    except Exception as e:
        await m.reply_text("❌ एरर: बॉट चैनल में Admin नहीं है या ID गलत है।")

# --- RUNNER ---
async def start_app():
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await bot.start()
    logger.info("✅ BOT AND STREAM ENGINE STARTED!")
    await idle()

if __name__ == "__main__":
    asyncio.run(start_app())
