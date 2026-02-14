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

bot = Client("uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- UPLOAD TO PIXELDRAIN ---
def upload_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        with open(file_path, "rb") as f:
            res = requests.post(url, files={"file": f})
        
        # Pixeldrain 200 या 201 दोनों भेज सकता है
        if res.status_code in [200, 201]:
            data = res.json()
            file_id = data.get("id")
            return f"https://pixeldrain.com/api/file/{file_id}?filename=video.mp4"
    except Exception as e:
        logger.error(f"Pixeldrain Error: {e}")
    return None

# --- UPLOAD TO CATBOX (Backup) ---
def upload_catbox(file_path):
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        with open(file_path, "rb") as f:
            res = requests.post(url, data=data, files={"fileToUpload": f})
        if res.status_code == 200:
            return res.text.strip() # यह सीधा .mp4 लिंक देता है
    except Exception as e:
        logger.error(f"Catbox Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="✅ Bot is Running!")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("👋 नमस्ते! वीडियो या फाइल भेजें, मैं आपको **Direct MP4 Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status = await m.reply_text("⏳ फाइल डाउनलोड हो रही है...", quote=True)
        file_path = None
        try:
            file_path = await m.download()
            await status.edit_text("🚀 सर्वर पर अपलोड हो रहा है...")
            
            # पहले Pixeldrain ट्राई करें
            link = upload_pixeldrain(file_path)
            
            # अगर Pixeldrain फेल हो, तो Catbox ट्राई करें
            if not link:
                await status.edit_text("🔄 Pixeldrain फेल हुआ, Backup सर्वर पर भेज रहा हूँ...")
                link = upload_catbox(file_path)
            
            if link:
                await status.edit_text(f"✅ **Link Ready!**\n\n🔗 `{link}`\n\nइसे एडमिन पैनल में लगायें।")
            else:
                await status.edit_text("❌ दोनों सर्वर फेल हो गए। कृपया रेंडर के Logs चेक करें।")
                
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
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
