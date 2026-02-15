import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web
import urllib.parse

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "8000"))
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip('/')

# Bot initialization
bot = Client("proxy_stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- STREAMING HANDLER ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        
        # File ID se message fetch karo
        try:
            msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        except Exception as e:
            logger.error(f"Message fetch error: {e}")
            return web.Response(text="File not found in channel!", status=404)
        
        if not msg or (not msg.video and not msg.document and not msg.audio):
            return web.Response(text="No video/document found in this message!", status=404)
        
        # File type detect karo
        if msg.video:
            file = msg.video
            mime_type = "video/mp4"
        elif msg.document:
            file = msg.document
            mime_type = file.mime_type or "video/mp4"
        elif msg.audio:
            file = msg.audio
            mime_type = file.mime_type or "audio/mpeg"
        else:
            return web.Response(text="Unsupported file type!", status=400)
        
        file_size = file.file_size
        file_name = file.file_name or f"stream_{file_id}.mp4"
        
        # Range header parse karo (for seeking)
        range_header = request.headers.get("Range", "")
        start = 0
        end = file_size - 1
        
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
        
        # Content length calculate karo
        content_length = end - start + 1
        
        # Headers set karo
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            "Content-Disposition": f'inline; filename="{urllib.parse.quote(file_name)}"',
        }
        
        # Agar range request hai to 206 Partial Content bhejo
        status = 206 if range_header else 200
        if range_header:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        
        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)
        
        # Direct download from Telegram
        try:
            # Pyrogram ka download handler use karo
            downloaded = 0
            current_chunk = start
            chunk_size = 1024 * 1024  # 1MB chunks
            
            async for chunk in bot.stream_media(msg, limit=chunk_size):
                chunk_len = len(chunk)
                
                # Skip unwanted chunks (seeking ke liye)
                if current_chunk + chunk_len <= start:
                    current_chunk += chunk_len
                    continue
                
                # Partial chunk handle karo
                chunk_start = max(0, start - current_chunk)
                chunk_end = min(chunk_len, end - current_chunk + 1)
                
                if chunk_start < chunk_end:
                    await response.write(chunk[chunk_start:chunk_end])
                    downloaded += (chunk_end - chunk_start)
                
                current_chunk += chunk_len
                
                # Agar required data mil gaya to break
                if downloaded >= content_length:
                    break
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            # Agar connection close ho gaya to ignore karo
            pass
            
        return response
        
    except Exception as e:
        logger.error(f"Stream Handler Error: {e}")
        return web.Response(text=f"Error: {str(e)}", status=500)

# --- HOME PAGE ---
async def home(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Stream Bot</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #0088cc; }
            .info { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>✅ Telegram Stream Bot is Running!</h1>
        <div class="info">
            <p>Send any video to the bot to get a direct stream link.</p>
            <p>Bot: @YourBotUsername</p>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    welcome_text = """
👋 नमस्ते! मैं एक **Telegram Video Stream Bot** हूँ।

📹 **कैसे use करें:**
• मुझे कोई भी वीडियो भेजें
• मैं आपको Direct Stream Link दूंगा
• उस link को किसी भी player में open करें

⚡ **Features:**
• Direct streaming (no download)
• Range support (seeking)
• Multiple file types

🆓 **Free & Fast!**
    """
    await message.reply_text(welcome_text)

@bot.on_message((filters.video | filters.document | filters.audio) & filters.private)
async def handle_media(client, message):
    try:
        # Progress message
        status_msg = await message.reply_text("⏳ Processing...")
        
        # Channel me forward karo
        forwarded = await message.copy(CHANNEL_ID)
        
        # Stream link generate karo
        stream_link = f"{BASE_URL}/stream/{forwarded.id}"
        
        # File info
        if message.video:
            file_name = message.video.file_name or "video.mp4"
            file_size = message.video.file_size
        elif message.document:
            file_name = message.document.file_name or "document.mp4"
            file_size = message.document.file_size
        else:
            file_name = message.audio.file_name or "audio.mp3"
            file_size = message.audio.file_size
        
        # Size format karo
        if file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
        
        # Reply message
        reply_text = f"""
✅ **Stream Link Generated!**

📁 **File:** `{file_name}`
📦 **Size:** {size_str}
🔗 **Link:** `{stream_link}`

📱 **Use in:**
• VLC Media Player
• MX Player
• Chrome/Firefox
• Any video player

⏱️ **Link is permanent!**
        """
        
        await status_msg.delete()
        await message.reply_text(reply_text)
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

# --- MAIN FUNCTION ---
async def main():
    # Web app setup
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/stream/{id}", stream_handler)
    
    # Web server start
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Web server running on port {PORT}")
    
    # Bot start
    await bot.start()
    logger.info("🤖 Bot started!")
    
    # Bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot username: @{bot_info.username}")
    logger.info(f"Base URL: {BASE_URL}")
    
    # Keep running
    await idle()
    
    # Cleanup
    await bot.stop()
    await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
