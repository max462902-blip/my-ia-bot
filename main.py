import os
import time
import math
import logging
import asyncio
from aiohttp import web
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Yahan apne Private Log Channel ki ID daalo (Bot wahan Admin hona chahiye)
# Example: LOG_CHANNEL = -1001234567890
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "0")) 

# Render URL (Environment Variable mein add kar dena, ya auto detect hoga)
# Example: https://my-bot.onrender.com
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

# --- SETUP ---
logging.basicConfig(level=logging.INFO)
bot = Client("stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)

# --- WEB SERVER (STREAMER) ---
async def stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        file_name = request.match_info['file_name']
        
        # Telegram se file maangna
        msg = await bot.get_messages(LOG_CHANNEL, message_id)
        media = msg.video or msg.document or msg.audio
        
        if not media:
            return web.Response(status=404, text="File Not Found")

        file_size = media.file_size
        
        # Range Header Handle karna (Video seeking ke liye zaroori hai)
        range_header = request.headers.get('Range')
        from_bytes, until_bytes = 0, file_size - 1
        
        if range_header:
            from_bytes, until_bytes = 0, file_size - 1
            s_range = range_header.replace('bytes=', '').split('-')
            from_bytes = int(s_range[0])
            if len(s_range) > 1 and s_range[1]:
                until_bytes = int(s_range[1])
        
        length = until_bytes - from_bytes + 1
        headers = {
            'Content-Type': media.mime_type or 'application/octet-stream',
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {from_bytes}-{until_bytes}/{file_size}',
            'Content-Length': str(length),
            'Content-Disposition': f'inline; filename="{file_name}"' 
        }

        # Response Generator
        resp = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await resp.prepare(request)

        # Telegram se chunks download karke Browser ko bhejna
        async for chunk in bot.download_media(msg, offset=from_bytes, limit=length, in_memory=True, chunk_size=1024*1024):
            await resp.write(chunk)
        
        return resp

    except Exception as e:
        print(f"Stream Error: {e}")
        return web.Response(status=500, text="Internal Server Error")

async def home(request):
    return web.Response(text="Bot is Live and Streaming!")

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Streamer Bot Ready!**\nFile bhejo, main Direct Link dunga.")

@bot.on_message(filters.video | filters.document)
async def handle_file(client, message):
    if LOG_CHANNEL == 0:
        return await message.reply_text("❌ Error: LOG_CHANNEL ID set nahi hai.")

    status = await message.reply_text("🔄 **Processing...**")
    
    try:
        # 1. File Name Safai
        media = message.video or message.document
        original_name = getattr(media, "file_name", f"video_{message.id}.mp4")
        safe_name = original_name.replace(" ", "_").replace("(", "").replace(")", "")
        
        # 2. File ko Log Channel mein Forward karna (Permanent Storage)
        log_msg = await message.copy(LOG_CHANNEL)
        
        # 3. Link Generate Karna
        # Link Format: https://your-site.com/watch/MESSAGE_ID/FILE_NAME
        stream_link = f"{BASE_URL}/watch/{log_msg.id}/{safe_name}"
        
        # 4. Reply
        await status.edit(
            f"✅ **File Saved Permanently!**\n\n"
            f"🔗 **Direct Link:**\n`{stream_link}`\n\n"
            f"⚠️ *Ye link tab tak chalega jab tak Bot Render par ON hai.*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Open in Chrome / Play", url=stream_link)]
            ])
        )

    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# --- STARTUP ---
async def start_services():
    # Web Server Setup
    app = web.Application()
    app.router.add_get('/', home)
    app.router.add_get('/watch/{message_id}/{file_name}', stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Render PORT variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Bot Start
    print("Bot & Server Starting...")
    await bot.start()
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_services())
