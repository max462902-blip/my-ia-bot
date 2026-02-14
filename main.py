import os
import asyncio
import logging
from pyrogram import Client, filters
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

# --- STREAMING ENGINE ---
async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        
        # वीडियो चलाने के लिए जरूरी सेटिंग्स
        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Length": str(file.file_size),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)

        # फाइल को टेलीग्राम से सीधा आगे भेजना
        async for chunk in bot.iter_download(file.file_id):
            await response.write(chunk)
            
        return response
    except Exception as e:
        return web.Response(text=str(e), status=500)

async def home_handler(request):
    return web.Response(text="✅ Bot & Streaming Engine are Running!", content_type="text/html")

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    logger.info(f"User {m.from_user.id} started the bot")
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nवीडियो भेजें, मैं **Direct MP4 Link** दूँगा जो आपके ऐप में चलेगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def get_link(c, m):
    try:
        log_msg = await m.copy(CHANNEL_ID)
        raw_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        base_url = raw_url.rstrip('/')
        stream_link = f"{base_url}/file/{log_msg.id}"
        
        await m.reply_text(f"✅ **Video Ready!**\n\n🔗 `{stream_link}`")
    except Exception as e:
        await m.reply_text("❌ एरर: बॉट चैनल में Admin नहीं है।")

# --- MAIN RUNNER (The Stable Way) ---
async def main():
    # वेब सर्वर चालू करें
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    # बॉट चालू करें
    await bot.start()
    logger.info("✅ BOT STARTED SUCCESSFULLY!")
    
    # बॉट को चालू रखने का सबसे स्थिर तरीका
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
