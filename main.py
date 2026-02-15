import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# 1. Logging Setup
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. Configuration
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

# बॉट क्लाइंट
bot = Client("my_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER LOGIC ---
async def home_handler(request):
    return web.Response(text="✅ बॉट ऑनलाइन है और रिप्लाई देने के लिए तैयार है!", content_type="text/html")

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        
        # Check if file_id is valid number
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID", status=400)
            
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        if not msg or (not msg.video and not msg.document and not msg.audio and not msg.photo):
            return web.Response(text="File not found!", status=404)
        
        # Get the media file
        file = None
        if msg.video:
            file = msg.video
        elif msg.document:
            file = msg.document
        elif msg.audio:
            file = msg.audio
        elif msg.photo:
            file = msg.photo
        else:
            return web.Response(text="No media found", status=404)
        
        # Handle Range header for streaming
        range_header = request.headers.get("Range")
        file_size = file.file_size
        
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            start = int(match.group(1)) if match else 0
            end = int(match.group(2)) if match and match.group(2) else file_size - 1
            
            # Ensure valid range
            if start >= file_size or end >= file_size:
                return web.Response(
                    status=416,
                    headers={"Content-Range": f"bytes */{file_size}"},
                    text="Range Not Satisfiable"
                )
            
            headers = {
                "Content-Type": file.mime_type or "application/octet-stream",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str((end - start) + 1),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file.file_name or "video.mp4"}"'
            }
            response = web.StreamResponse(status=206, headers=headers)
        else:
            # No range header, send entire file
            headers = {
                "Content-Type": file.mime_type or "application/octet-stream",
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file.file_name or "video.mp4"}"'
            }
            response = web.StreamResponse(status=200, headers=headers)
            start = 0
        
        await response.prepare(request)
        
        # Download and stream file in chunks
        chunk_size = 1024 * 1024  # 1MB chunks
        current_position = start
        
        async for chunk in bot.stream_media(msg, limit=chunk_size, offset=current_position):
            await response.write(chunk)
            current_position += len(chunk)
            if current_position > (end if range_header else file_size - 1):
                break
        
        return response
        
    except Exception as e:
        logger.error(f"Streaming Error: {str(e)}")
        return web.Response(text=f"Error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    logger.info(f"Start command received from {m.from_user.id}")
    await m.reply_text(
        f"नमस्ते {m.from_user.first_name}!\n\n"
        f"बॉट चालू है। मुझे कोई भी वीडियो फॉरवर्ड करें, मैं आपको उसका **Direct MP4 Link** दूँगा।\n\n"
        f"⚠️ **नोट:** बॉट को चैनल में एडमिन होना जरूरी है!"
    )

@bot.on_message((filters.video | filters.document | filters.audio) & filters.private)
async def handle_media(c, m):
    try:
        sent_msg = await m.reply_text("⏳ लिंक बन रहा है, कृपया प्रतीक्षा करें...", quote=True)
        
        # Copy message to channel
        log_msg = await m.copy(CHANNEL_ID)
        
        # Get base URL
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        
        # Get filename
        if m.video:
            filename = m.video.file_name or "video.mp4"
        elif m.document:
            filename = m.document.file_name or "document.mp4"
        elif m.audio:
            filename = m.audio.file_name or "audio.mp3"
        else:
            filename = "media.mp4"
        
        # Generate streaming link
        stream_link = f"{base_url}/file/{log_msg.id}"
        
        # Create different links for different purposes
        direct_link = f"{stream_link}?filename={filename}"
        embed_link = f'{base_url}/file/{log_msg.id}'
        
        await sent_msg.edit_text(
            f"✅ **लिंक तैयार है!**\n\n"
            f"📹 **Direct Link:**\n`{direct_link}`\n\n"
            f"🔗 **Embed Link:**\n`{embed_link}`\n\n"
            f"📁 **File Name:** `{filename}`\n"
            f"📦 **File Size:** `{file_size_format(file_size)}`\n\n"
            f"💡 इसे अपने एडमिन पैनल या वेबसाइट में लगायें।"
        )
        
    except Exception as e:
        logger.error(f"Copy Error: {str(e)}")
        await m.reply_text(
            "❌ एरर: बॉट चैनल में Admin नहीं है या कोई अन्य त्रुटि हुई।\n\n"
            "कृपया चेक करें:\n"
            "1. बॉट को चैनल में एडमिन बनाया गया है?\n"
            "2. CHANNEL_ID सही है?\n"
            "3. बॉट टोकन सही है?"
        )

def file_size_format(size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

# --- MAIN RUNNER ---
async def main():
    try:
        # Start web server
        app = web.Application()
        app.router.add_get("/", home_handler)
        app.router.add_get("/file/{id}", stream_handler)
        app.router.add_get("/file/{id}/", stream_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🌐 Web Server started on port {PORT}")

        # Start bot
        await bot.start()
        
        # Get bot info
        bot_info = await bot.get_me()
        logger.info(f"✅ बॉट @{bot_info.username} सफलतापूर्वक शुरू हो गया है!")
        
        # Verify channel access
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            logger.info(f"📢 Channel connected: {chat.title} (ID: {CHANNEL_ID})")
        except Exception as e:
            logger.error(f"❌ Channel access error: {e}")
            logger.error("कृपया सुनिश्चित करें कि बॉट चैनल में एडमिन है!")
        
        await idle()
        
    except Exception as e:
        logger.error(f"Main Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
