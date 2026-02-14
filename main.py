import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("streaming_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- STREAMING ENGINE (Range Support) ---
async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)
        
        file = msg.video or msg.document
        file_size = file.file_size
        range_header = request.headers.get("Range")

        # Range Logic for Players
        start = 0
        end = file_size - 1
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))

        calc_length = (end - start) + 1

        headers = {
            "Content-Type": file.mime_type or "video/mp4",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(calc_length),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await response.prepare(request)

        # Telegram से सीधा डेटा स्ट्रीम करना
        async for chunk in bot.iter_download(file.file_id, offset=start):
            await response.write(chunk)
            
        return response
    except Exception as e:
        return web.Response(text=str(e), status=500)

async def home_handler(request):
    return web.Response(text="✅ Video Streaming Engine is Live!", content_type="text/html")

# --- COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("नमस्ते! मुझे वीडियो भेजें, मैं **Direct Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def get_link(c, m):
    log_msg = await m.copy(CHANNEL_ID)
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip('/')
    stream_link = f"{base_url}/file/{log_msg.id}"
    await m.reply_text(f"✅ **Link Ready:**\n\n`{stream_link}`")

# --- RUNNER ---
async def start_services():
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await bot.start()
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_services())
