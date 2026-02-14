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
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("multi_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- UPLOAD TO CATBOX (Permanent - Max 200MB) ---
async def upload_catbox(file_path):
    try:
        url = "https://catbox.moe/user/api.php"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('userhash', '')
            data.add_field('fileToUpload', open(file_path, 'rb'))
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception as e:
        logger.error(f"Catbox Error: {e}")
    return None

# --- UPLOAD TO PIXELDRAIN (60 Days - Max 10GB) ---
async def upload_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', open(file_path, 'rb'))
            async with session.post(url, data=data) as resp:
                if resp.status in [200, 201]:
                    res_json = await resp.json()
                    file_id = res_json.get("id")
                    return f"https://pixeldrain.com/api/file/{file_id}?filename=video.mp4"
    except Exception as e:
        logger.error(f"Pixeldrain Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="✅ Bot is Online and Ready!")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("👋 नमस्ते! वीडियो भेजें।\n\n✅ <200MB: Catbox (Permanent)\n✅ >200MB: Pixeldrain (60 Days)")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status = await m.reply_text("📥 रेंडर सर्वर में डाउनलोड हो रहा है...", quote=True)
        file_path = None
        try:
            file_path = await m.download()
            file_size = os.path.getsize(file_path) / (1024 * 1024) # Size in MB

            link = None
            if file_size < 200:
                await status.edit_text("🚀 Catbox पर अपलोड हो रहा है (Permanent Link)...")
                link = await upload_catbox(file_path)
            
            if not link: # बड़ी फाइल या Catbox फेल होने पर Pixeldrain
                await status.edit_text("🚀 Pixeldrain पर अपलोड हो रहा है...")
                link = await upload_pixeldrain(file_path)

            if link:
                await status.edit_text(f"✅ **Upload Success!**\n\n🔗 `{link.strip()}`\n\nइसे एडमिन पैनल में लगायें।")
            else:
                await status.edit_text("❌ अपलोड फेल हो गया।")
                
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
