import os
import asyncio
import logging
import re
from pyrogram import Client, filters, idle
from aiohttp import web

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration - अब सही CHANNEL_ID के साथ
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8208753129:AAHxLUPLP4HexecIgPq2Yr1136Hl8kwnc2E")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))  # ✅ आपकी सही चैनल ID
PORT = int(os.environ.get("PORT", "10000"))

# बॉट क्लाइंट
bot = Client("my_link_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER ---
async def home_handler(request):
    return web.Response(text="✅ बॉट ऑनलाइन है!", content_type="text/html")

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID", status=400)
            
        # चैनल से मैसेज लाएं
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg or not (msg.video or msg.document or msg.audio):
            return web.Response(text="File not found!", status=404)
        
        # मीडिया फाइल प्राप्त करें
        file = msg.video or msg.document or msg.audio
        
        # Streaming headers
        range_header = request.headers.get("Range")
        file_size = file.file_size
        file_name = getattr(file, 'file_name', 'video.mp4')
        
        if range_header:
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            start = int(match.group(1)) if match else 0
            end = int(match.group(2)) if match and match.group(2) else file_size - 1
            
            headers = {
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str((end - start) + 1),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_name}"'
            }
            response = web.StreamResponse(status=206, headers=headers)
        else:
            headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_name}"'
            }
            response = web.StreamResponse(status=200, headers=headers)
            start = 0
        
        await response.prepare(request)
        
        # फाइल स्ट्रीम करें
        async for chunk in bot.stream_media(msg, offset=start, limit=1024*1024):
            await response.write(chunk)
            if len(chunk) < 1024*1024:
                break
        
        return response
        
    except Exception as e:
        logger.error(f"Streaming Error: {str(e)}")
        return web.Response(text=f"Error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(
        f"नमस्ते {m.from_user.first_name}! 👋\n\n"
        f"मैं वीडियो लिंक जनरेटर बॉट हूं।\n"
        f"मुझे कोई भी वीडियो या फाइल भेजें, मैं आपको Direct Streaming Link दूंगा।\n\n"
        f"📌 चैनल: @videoslinkmp4"
    )

@bot.on_message((filters.video | filters.document | filters.audio) & filters.private)
async def handle_media(c, m):
    try:
        # प्रोसेसिंग मैसेज
        processing_msg = await m.reply_text("⏳ लिंक बन रहा है... कृपया प्रतीक्षा करें", quote=True)
        
        # चैनल में मैसेज कॉपी करें
        logger.info(f"Copying media to channel {CHANNEL_ID}")
        channel_msg = await m.copy(CHANNEL_ID)
        logger.info(f"✅ Media copied successfully! Message ID: {channel_msg.id}")
        
        # लिंक जनरेट करें
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
        
        # फाइल का नाम प्राप्त करें
        if m.video:
            file_name = m.video.file_name or "video.mp4"
            file_size = m.video.file_size
        elif m.document:
            file_name = m.document.file_name or "document.mp4"
            file_size = m.document.file_size
        elif m.audio:
            file_name = m.audio.file_name or "audio.mp3"
            file_size = m.audio.file_size
        else:
            file_name = "media.mp4"
            file_size = 0
        
        # स्ट्रीमिंग लिंक
        stream_link = f"{base_url}/file/{channel_msg.id}"
        
        # फाइल साइज फॉर्मेट करें
        size_str = format_file_size(file_size)
        
        await processing_msg.edit_text(
            f"✅ **आपका लिंक तैयार है!**\n\n"
            f"📹 **वीडियो:** `{file_name}`\n"
            f"📦 **साइज:** {size_str}\n\n"
            f"🔗 **स्ट्रीमिंग लिंक:**\n"
            f"`{stream_link}`\n\n"
            f"📌 **Embed Code:**\n"
            f"`<video src='{stream_link}' controls width='100%'></video>`\n\n"
            f"💡 इस लिंक को अपने एडमिन पैनल या वेबसाइट में इस्तेमाल करें।"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_media: {str(e)}")
        error_msg = str(e).lower()
        
        if "chat not found" in error_msg or "identifier" in error_msg:
            await m.reply_text(
                "❌ **चैनल ID गलत है!**\n\n"
                "कृपया चेक करें:\n"
                "1. CHANNEL_ID = -1003800002652 सही है?\n"
                "2. बॉट को चैनल में एडमिन बनाया गया है?"
            )
        elif "admin" in error_msg or "privileges" in error_msg:
            await m.reply_text(
                "❌ **बॉट एडमिन नहीं है!**\n\n"
                "कृपया @videoslinkmp4 चैनल में जाकर बॉट को एडमिन बनाएं।"
            )
        else:
            await m.reply_text(f"❌ एरर: {str(e)}")

def format_file_size(size):
    """फाइल साइज को ह्यूमन रीडेबल फॉर्मेट में बदलें"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

@bot.on_message(filters.command("channel") & filters.private)
async def channel_cmd(c, m):
    """चैनल की जानकारी दिखाएं"""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        await m.reply_text(
            f"📢 **चैनल जानकारी:**\n\n"
            f"नाम: {chat.title}\n"
            f"ID: `{chat.id}`\n"
            f"लिंक: {chat.invite_link or 'https://t.me/videoslinkmp4'}\n\n"
            f"✅ बॉट इस चैनल से कनेक्ट है!"
        )
    except Exception as e:
        await m.reply_text(f"❌ चैनल कनेक्ट नहीं है: {str(e)}")

async def main():
    # वेब सर्वर शुरू करें
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", stream_handler)
    app.router.add_get("/file/{id}/", stream_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Web Server started on port {PORT}")

    # बॉट शुरू करें
    await bot.start()
    
    # बॉट की जानकारी
    me = await bot.get_me()
    logger.info(f"✅ बॉट @{me.username} शुरू हो गया है!")
    
    # चैनल कनेक्शन चेक करें
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        logger.info(f"📢 चैनल कनेक्टेड: {chat.title}")
        
        # चेक करें कि बॉट एडमिन है या नहीं
        try:
            member = await bot.get_chat_member(CHANNEL_ID, "me")
            if member.status in ["administrator", "creator"]:
                logger.info("✅ बॉट एडमिन है - सब ठीक है!")
            else:
                logger.warning("⚠️ बॉट एडमिन नहीं है! चैनल में बॉट को एडमिन बनाएं।")
        except:
            logger.warning("⚠️ बॉट की एडमिन स्टेटस चेक नहीं हो सकी")
            
    except Exception as e:
        logger.error(f"❌ चैनल कनेक्ट नहीं है: {e}")
        logger.error("कृपया CHANNEL_ID = -1003800002652 चेक करें")
    
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
