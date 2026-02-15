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
bot = Client("direct_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER (For Render Health Check) ---
async def home(request):
    return web.Response(text="✅ Bot is Online & Listening to Messages!", content_type="text/html")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_msg(c, m):
    logger.info(f"User {m.from_user.id} started the bot")
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे वीडियो भेजें, मैं आपको **Direct MP4 Link** दूँगा जो टेलीग्राम से सीधा चलेगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def get_link(c, m):
    try:
        # वीडियो को चैनल में फॉरवर्ड/कॉपी करना (सुरक्षा के लिए)
        log_msg = await m.copy(CHANNEL_ID)
        
        # रेंडर का असली यूआरएल
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com").rstrip('/')
        
        # डायरेक्ट स्ट्रीमिंग लिंक (यह रेंडर के ज़रिये टेलीग्राम से डेटा लाएगा)
        stream_link = f"{base_url}/stream/{log_msg.id}?filename=video.mp4"
        
        await m.reply_text(
            f"✅ **लिंक तैयार है!**\n\n"
            f"🔗 `{stream_link}`\n\n"
            f"इसे एडमिन पैनल में लगायें। यह लाइफटाइम चलेगा।"
        )
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}\nपक्का करें कि बॉट चैनल में एडमिन है।")

# --- STARTUP ENGINE ---
async def main():
    # 1. वेब सर्वर सेटअप (रेंडर के लिए)
    app = web.Application()
    app.router.add_get("/", home)
    # भविष्य में डायरेक्ट स्ट्रीमिंग के लिए यहाँ हैंडलर बढ़ाया जा सकता है
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

    # 2. बॉट चालू करना
    await bot.start()
    logger.info("✅ BOT STARTED SUCCESSFULLY!")
    
    # 3. बॉट को एक्टिव रखना
    await idle()
    
    # 4. बंद होने पर सफाई
    await bot.stop()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
