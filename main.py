import os
import asyncio
import aiohttp
import logging
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "") # नया फ्रेश टोकन डालें
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("chrome_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- PIXELDRAIN ASYNC UPLOADER ---
async def upload_to_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f)
                async with session.post(url, data=data) as resp:
                    if resp.status in [200, 201]:
                        res_json = await resp.json()
                        file_id = res_json.get("id")
                        # यह लिंक Chrome और App दोनों के लिए अमृत है
                        return f"https://pixeldrain.com/api/file/{file_id}?filename=video.mp4"
    except Exception as e:
        logger.error(f"Upload Error: {e}")
    return None

# --- WEB SERVER (Render Check) ---
async def home(request):
    return web.Response(text="✅ Chrome Link Generator is Live!", content_type="text/html")

# --- HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("नमस्ते! वीडियो भेजें, मैं आपको **Chrome और App** में चलने वाला Direct लिंक दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status = await m.reply_text("📥 Chrome के लिए फाइल तैयार हो रही है (Downloading)...", quote=True)
        file_path = None
        try:
            file_path = await m.download()
            await status.edit_text("🚀 सर्वर पर चढ़ाया जा रहा है (Uploading)...")
            
            link = await upload_to_pixeldrain(file_path)
            
            if link:
                await status.edit_text(
                    f"✅ **Link Ready for Chrome & App!**\n\n"
                    f"🔗 `{link}`\n\n"
                    f"इसे एडमिन पैनल में लगायें। यह कभी नहीं अटकेगा।"
                )
            else:
                await status.edit_text("❌ अपलोड फेल हो गया। शायद फाइल 500MB से बड़ी है।")
                
        except Exception as e:
            await status.edit_text(f"❌ एरर: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

async def main():
    app = web.Application()
    app.router.add_get("/", home)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await bot.start()
    logger.info("✅ BOT STARTED")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
