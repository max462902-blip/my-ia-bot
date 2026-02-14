import os
import asyncio
import requests
import logging
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("pixeldrain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- WEB SERVER (Render Health Check) ---
async def home_handler(request):
    return web.Response(text="✅ Uploader Bot is Running!", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", home_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

# --- PIXELDRAIN ENGINE ---
def upload_to_pixeldrain(file_path):
    try:
        with open(file_path, 'rb') as f:
            response = requests.post("https://pixeldrain.com/api/file/", files={"file": f})
        if response.status_code == 201:
            file_id = response.json()["id"]
            return f"https://pixeldrain.com/api/file/{file_id}?filename=video.mp4"
        return None
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        return None

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("👋 नमस्ते! वीडियो भेजें, मैं Pixeldrain पर अपलोड करके Direct MP4 लिंक दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status_msg = await m.reply_text("📥 डाउनलोड हो रहा है...", quote=True)
        file_path = None
        try:
            file_path = await m.download()
            await status_msg.edit_text("🚀 Pixeldrain पर अपलोड हो रहा है...")
            direct_link = upload_to_pixeldrain(file_path)
            if direct_link:
                await status_msg.edit_text(f"✅ **Upload Success!**\n\n🔗 `{direct_link}`\n\nइसे एडमिन पैनल में लगायें।")
            else:
                await status_msg.edit_text("❌ अपलोड फेल हो गया।")
        except Exception as e:
            await status_msg.edit_text(f"❌ एरर: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# --- MAIN STARTUP ---
async def main():
    await start_web_server()
    await bot.start()
    logger.info("✅ Bot is Live!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
