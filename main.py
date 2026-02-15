import os
import asyncio
import logging
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

# --- WEB SERVER (Render को खुश रखने के लिए) ---
async def home(request):
    return web.Response(text="✅ Bot is Online & Listening!", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", home)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    logger.info(f"Start command from {m.from_user.id}")
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे वीडियो भेजें, मैं आपको **Direct MP4 Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_forward(c, m):
    try:
        # वीडियो चैनल में कॉपी करें
        log_msg = await m.copy(CHANNEL_ID)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com").rstrip('/')
        
        # डायरेक्ट स्ट्रीम लिंक
        stream_link = f"{base_url}/file/{log_msg.id}?filename=video.mp4"
        
        await m.reply_text(f"✅ **लिंक तैयार है!**\n\n🔗 `{stream_link}`")
    except Exception as e:
        logger.error(f"Error: {e}")
        await m.reply_text("❌ एरर: बॉट चैनल में Admin नहीं है।")

# --- MAIN RUNNER (The Fix) ---
async def main():
    # 1. पहले वेब सर्वर शुरू करें
    await start_web_server()
    
    # 2. फिर बॉट शुरू करें
    await bot.start()
    logger.info("✅ BOT STARTED SUCCESSFULLY!")
    
    # 3. बॉट को रिप्लाई सुनने के लिए 'idle' रखें
    await idle()
    
    # 4. सफाई
    await bot.stop()

if __name__ == "__main__":
    # Event Loop को सही से चलाने के लिए
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
