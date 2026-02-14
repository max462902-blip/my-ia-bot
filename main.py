import os
import asyncio
import logging
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

# बॉट सेटअप
bot = Client("link_master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER HANDLERS ---
async def home_handler(request):
    return web.Response(text="✅ Bot is Online & Listening!", content_type="text/html")

async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Length": str(file.file_size),
            "Accept-Ranges": "bytes",
        }
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        async for chunk in bot.iter_download(file.file_id):
            await response.write(chunk)
        return response
    except Exception as e:
        return web.Response(text=str(e), status=500)

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nवीडियो भेजें, मैं **Direct Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_video(c, m):
    try:
        sent_msg = await m.reply_text("⏳ लिंक बन रहा है...", quote=True)
        log_msg = await m.copy(CHANNEL_ID)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{log_msg.id}"
        await sent_msg.edit_text(f"✅ **लिंक तैयार है!**\n\n🔗 `{stream_link}`")
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}")

# --- STARTUP LOGIC ---
async def start_services():
    # 1. वेब सर्वर सेटअप
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    
    # 2. दोनों को साथ में शुरू करना
    await site.start()
    logger.info(f"Web Server started on port {PORT}")
    
    await bot.start()
    logger.info("Bot started and polling for messages...")
    
    # 3. बॉट को "Active" रखना
    await idle()
    
    # 4. बंद होने पर सफाई (Cleanup)
    await bot.stop()
    await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
