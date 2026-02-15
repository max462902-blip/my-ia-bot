import os
import asyncio
import aiohttp
import logging
import re
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

bot = Client("cdn_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1) # à¤ à¤• à¤¬à¤¾à¤° à¤®à¥‡à¤‚ à¤¸à¤¿à¤°à¥ à¤« à¤ à¤• à¤…à¤ªà¤²à¥‹à¤¡ (RAM à¤¬à¤šà¤¾à¤¨à¥‡ à¤•à¥‡ à¤²à¤¿à¤¯à¥‡)

# --- UPLOAD TO GOFILE (CDN Speed) ---
async def upload_gofile(file_path):
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Get Best Server
            async with session.get("https://api.gofile.io/getServer") as r:
                res = await r.json()
                if res["status"] != "ok": return None
                server = res["data"]["server"]

            # 2. Upload File
            url = f"https://{server}.gofile.io/uploadFile"
            data = aiohttp.FormData()
            data.add_field('file', open(file_path, 'rb'))
            
            async with session.post(url, data=data) as resp:
                res_json = await resp.json()
                if res_json["status"] == "ok":
                    # à¤¸à¥€à¤§à¤¾ Download Page link
                    return res_json["data"]["downloadPage"]
    except Exception as e:
        logger.error(f"Gofile Error: {e}")
    return None

# --- UPLOAD TO PIXELDRAIN (Backup) ---
async def upload_pixeldrain(file_path):
    try:
        url = "https://pixeldrain.com/api/file"
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', open(file_path, 'rb'))
            async with session.post(url, data=data) as resp:
                if resp.status in [200, 201]:
                    res_json = await resp.json()
                    return f"https://pixeldrain.com/api/file/{res_json['id']}?filename=video.mp4"
    except Exception as e:
        logger.error(f"Pixeldrain Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="Bot is Live with CDN Support!")

# --- HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("âœ… बॉट तैयार है! बड़ी फाइल (450MB तक) भेजें, मैं लिंक दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status = await m.reply_text("â ³ रेंडर सर्वर पर डाउनलोड हो रहा है...", quote=True)
        file_path = None
        try:
            file_path = await m.download()
            await status.edit_text("ðŸš€ CDN (Gofile) पर अपलोड हो रहा है...")
            
            # Gofile Try (Best for >200MB)
            link = await upload_gofile(file_path)
            
            if not link:
                await status.edit_text("ðŸ”„ Gofile फेल हुआ, Pixeldrain ट्राई कर रहा हूँ...")
                link = await upload_pixeldrain(file_path)
            
            if link:
                await status.edit_text(f"âœ… **CDN Link Ready!**\n\nðŸ”— `{link}`")
            else:
                await status.edit_text("â Œ दोनों सर्वर फेल हो गए। शायद रेंडर का इंटरनेट बंद हो गया।")
                
        except Exception as e:
            await status.edit_text(f"â Œ एरर: {e}")
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
    asyncio.run(main())
