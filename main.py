import os
import logging
import asyncio
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

# बॉट क्लाइंट
bot = Client("link_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (Health Check) ---
async def home_handler(request):
    return web.Response(text="✅ Bot is Online!", content_type="text/html")

async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        response = web.StreamResponse()
        response.content_type = file.mime_type or "video/mp4"
        response.content_length = file.file_size
        await response.prepare(request)
        
        async for chunk in bot.iter_download(file.file_id):
            await response.write(chunk)
        return response
    except Exception as e:
        return web.Response(text=str(e), status=500)

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    logger.info(f"Start command received from {m.from_user.id}")
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे वीडियो भेजें, मैं लिंक दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_forward(c, m):
    try:
        logger.info("Generating link...")
        log_msg = await m.copy(CHANNEL_ID)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        # परमानेंट लिंक बनाना
        stream_link = f"{base_url.rstrip('/')}/file/{log_msg.id}"
        await m.reply_text(f"✅ **Link Generated!**\n\n🔗 `{stream_link}`")
    except Exception as e:
        logger.error(f"Error generating link: {e}")
        await m.reply_text("❌ एरर: बॉट चैनल में एडमिन नहीं है।")

# --- MAIN RUNNER ---
async def start_bot():
    # वेब सर्वर सेटअप
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    
    logger.info("Starting Web Server...")
    await site.start()
    
    logger.info("Starting Telegram Bot...")
    await bot.start()
    
    logger.info("✅ BOT IS LIVE AND READY!")
    await idle() # बॉट को चालू रखने के लिए

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
