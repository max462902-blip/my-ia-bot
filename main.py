import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8208753129:AAHxLUPLP4HexecIgPq2Yr1136Hl8kwnc2E")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

# बॉट क्लाइंट
bot = Client("my_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER WITH MP4 LINKS ---
async def home_handler(request):
    return web.Response(
        text="""
        <html>
            <head><title>Video Link Bot</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>✅ बॉट ऑनलाइन है!</h1>
                <p>📢 चैनल: @videoslinkmp4</p>
                <p>🤖 बॉट: @Filelinkgunerterbot</p>
                <p>🔗 लिंक फॉर्मेट: /file/ID.mp4</p>
            </body>
        </html>
        """,
        content_type="text/html"
    )

async def stream_handler(request):
    try:
        # URL से file_id निकालें (.mp4 हटाकर)
        path = request.match_info.get("id", "")
        
        # अगर .mp4 है तो हटाएं, नहीं तो जैसा है वैसे रखें
        if path.endswith('.mp4'):
            file_id = path[:-4]  # .mp4 हटाएं
        else:
            file_id = path
            
        logger.info(f"📥 Stream request for file ID: {file_id}")
        
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID. Use format: /file/123.mp4", status=400)
        
        # चैनल से मैसेज लाएं
        try:
            msg = await asyncio.wait_for(
                bot.get_messages(CHANNEL_ID, int(file_id)),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.error("Timeout getting message from Telegram")
            return web.Response(text="Telegram timeout", status=504)
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return web.Response(text=f"Message not found: {str(e)}", status=404)
        
        if not msg:
            return web.Response(text="Message not found", status=404)
        
        # मीडिया चेक करें
        file = None
        file_name = "video.mp4"
        file_size = 0
        
        if msg.video:
            file = msg.video
            file_name = getattr(file, 'file_name', 'video.mp4') or 'video.mp4'
            if not file_name.endswith('.mp4'):
                file_name += '.mp4'
            file_size = file.file_size
            logger.info(f"🎬 Video found: {file_name}, Size: {file_size}")
        elif msg.document:
            file = msg.document
            file_name = getattr(file, 'file_name', 'document.mp4') or 'document.mp4'
            if not file_name.endswith(('.mp4', '.mkv', '.avi')):
                file_name += '.mp4'
            file_size = file.file_size
            logger.info(f"📄 Document found: {file_name}, Size: {file_size}")
        else:
            return web.Response(text="No video in this message", status=404)
        
        # Range header handling
        range_header = request.headers.get("Range")
        logger.info(f"📊 Range header: {range_header}")
        
        # Headers सेट करें
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_name}"',
            "Cache-Control": "public, max-age=3600",
        }
        
        if range_header and file_size > 0:
            # Parse range header
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                end_str = match.group(2)
                
                if start >= file_size:
                    return web.Response(
                        status=416,
                        headers={"Content-Range": f"bytes */{file_size}"},
                        text="Range Not Satisfiable"
                    )
                
                end = int(end_str) if end_str else file_size - 1
                end = min(end, file_size - 1)
                length = end - start + 1
                
                logger.info(f"📤 Serving bytes {start}-{end}/{file_size}")
                
                headers.update({
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                    "Content-Type": "video/mp4",
                })
                
                response = web.StreamResponse(status=206, headers=headers)
                await response.prepare(request)
                
                # Stream with timeout
                try:
                    downloaded = 0
                    async for chunk in bot.stream_media(msg, offset=start, limit=length):
                        await asyncio.wait_for(response.write(chunk), timeout=5.0)
                        downloaded += len(chunk)
                        if downloaded >= length:
                            break
                    logger.info(f"✅ Streamed {downloaded} bytes")
                except asyncio.TimeoutError:
                    logger.error("Timeout writing chunk")
                    return web.Response(text="Stream timeout", status=504)
                
                return response
        
        # No range header - send entire file
        logger.info(f"📤 Serving entire file: {file_size} bytes")
        headers.update({
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4",
        })
        
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        
        # Stream with timeout
        try:
            async for chunk in bot.stream_media(msg):
                await asyncio.wait_for(response.write(chunk), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("Timeout writing chunk")
            return web.Response(text="Stream timeout", status=504)
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Streaming Error: {str(e)}", exc_info=True)
        return web.Response(text=f"Streaming error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"🎥 **वीडियो लिंक जनरेटर बॉट**\n\n"
        f"मुझे कोई भी वीडियो भेजें, मैं आपको Direct Streaming Link दूंगा।\n\n"
        f"📌 **चैनल:** @videoslinkmp4\n"
        f"🤖 **बॉट:** @Filelinkgunerterbot\n\n"
        f"🔗 **लिंक फॉर्मेट:** `/file/ID.mp4`\n\n"
        f"**अभी एक वीडियो भेजें!** 🚀"
    )

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_media(c, m):
    temp_msg = None
    try:
        temp_msg = await m.reply_text("⏳ लिंक बन रहा है...", quote=True)
        
        # फाइल की जानकारी
        if m.video:
            file_name = m.video.file_name or f"video_{m.id}.mp4"
            file_size = m.video.file_size
        else:
            file_name = m.document.file_name or f"document_{m.id}.mp4"
            file_size = m.document.file_size
        
        # चैनल में कॉपी करें
        channel_msg = await m.copy(CHANNEL_ID)
        logger.info(f"✅ Copied! Message ID: {channel_msg.id}")
        
        # MP4 लिंक बनाएं
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://my-ia-bot-la0g.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{channel_msg.id}.mp4"
        
        # साइज फॉर्मेट करें
        size_str = format_file_size(file_size)
        
        await temp_msg.edit_text(
            f"✅ **आपका लिंक तैयार है!**\n\n"
            f"📹 **फाइल:** `{file_name}`\n"
            f"📦 **साइज:** {size_str}\n\n"
            f"🔗 **वीडियो लिंक (MP4):**\n"
            f"`{stream_link}`\n\n"
            f"🌐 **लिंक खोलें:** {stream_link}\n\n"
            f"💻 **एम्बेड कोड:**\n"
            f"`<video src='{stream_link}' controls width='100%'></video>`\n\n"
            f"📱 **लिंक पर क्लिक करें - वीडियो चलेगा!**"
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=True)
        error_text = f"❌ एरर: {str(e)}"
        if temp_msg:
            await temp_msg.edit_text(error_text)
        else:
            await m.reply_text(error_text)

def format_file_size(size):
    """फाइल साइज फॉर्मेट करें"""
    if not size or size <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

async def main():
    try:
        # वेब सर्वर शुरू करें
        app = web.Application()
        app.router.add_get("/", home_handler)
        app.router.add_get("/file/{id}", stream_handler)  # बिना .mp4 के भी काम करेगा
        app.router.add_get("/file/{id}.mp4", stream_handler)  # .mp4 के साथ भी
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🌐 Web Server started on port {PORT}")

        # बॉट शुरू करें
        await bot.start()
        me = await bot.get_me()
        logger.info(f"✅ बॉट @{me.username} शुरू हो गया है!")
        
        # चैनल चेक करें
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            logger.info(f"📢 चैनल मिला: {chat.title}")
        except Exception as e:
            logger.error(f"❌ चैनल एक्सेस नहीं हो सका: {e}")
        
        logger.info("🚀 बॉट तैयार है!")
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Main Error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
