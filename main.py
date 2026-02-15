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

# --- WEB SERVER WITH FIXED STREAMING ---
async def home_handler(request):
    return web.Response(
        text="""
        <html>
            <head><title>Video Link Bot</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>✅ बॉट ऑनलाइन है!</h1>
                <p>यह वीडियो स्ट्रीमिंग सर्वर है।</p>
                <p>बॉट को टेलीग्राम पर इस्तेमाल करें: @Filelinkgunerterbot</p>
            </body>
        </html>
        """,
        content_type="text/html"
    )

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        logger.info(f"Stream request for file ID: {file_id}")
        
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID", status=400)
        
        # चैनल से मैसेज लाएं
        try:
            msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return web.Response(text="Message not found in channel", status=404)
        
        if not msg:
            return web.Response(text="Message not found", status=404)
        
        # मीडिया चेक करें
        file = None
        if msg.video:
            file = msg.video
            logger.info(f"Video found: {file.file_name}, Size: {file.file_size}")
        elif msg.document:
            file = msg.document
            logger.info(f"Document found: {file.file_name}, Size: {file.file_size}")
        elif msg.audio:
            file = msg.audio
            logger.info(f"Audio found: {file.file_name}, Size: {file.file_size}")
        else:
            return web.Response(text="No media in this message", status=404)
        
        file_size = file.file_size
        file_name = getattr(file, 'file_name', 'video.mp4')
        
        # Range header handling for streaming
        range_header = request.headers.get("Range")
        logger.info(f"Range header: {range_header}")
        
        # Content-Type based on file extension
        content_type = "video/mp4"
        if file_name.endswith(('.mp3', '.m4a')):
            content_type = "audio/mpeg"
        elif file_name.endswith(('.jpg', '.jpeg', '.png')):
            content_type = "image/jpeg"
        
        if range_header:
            # Parse range header
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                end = match.group(2)
                end = int(end) if end else file_size - 1
                
                # Validate range
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
                length = end - start + 1
                
                logger.info(f"Serving bytes {start}-{end}/{file_size}")
                
                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                    "Content-Type": content_type,
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Cache-Control": "no-cache",
                }
                
                response = web.StreamResponse(status=206, headers=headers)
                await response.prepare(request)
                
                # Stream the specific chunk
                downloaded = 0
                async for chunk in bot.stream_media(msg, offset=start, limit=length):
                    await response.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= length:
                        break
                
                logger.info(f"Successfully streamed {downloaded} bytes")
                return response
        
        # No range header - send entire file
        logger.info(f"Serving entire file: {file_size} bytes")
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": content_type,
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_name}"',
        }
        
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        
        # Stream entire file
        async for chunk in bot.stream_media(msg):
            await response.write(chunk)
        
        return response
        
    except Exception as e:
        logger.error(f"Streaming Error: {str(e)}", exc_info=True)
        return web.Response(text=f"Streaming error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(
        f"👋 नमस्ते {m.from_user.first_name}!\n\n"
        f"🎥 **वीडियो लिंक जनरेटर बॉट**\n\n"
        f"मुझे कोई भी वीडियो या फाइल भेजें, मैं आपको Direct Streaming Link दूंगा।\n\n"
        f"📌 **चैनल:** @videoslinkmp4\n"
        f"🤖 **बॉट:** @Filelinkgunerterbot\n\n"
        f"✨ **फीचर्स:**\n"
        f"• डायरेक्ट स्ट्रीमिंग लिंक\n"
        f"• वेबसाइट में एम्बेड कर सकते हैं\n"
        f"• मोबाइल फ्रेंडली\n\n"
        f"अभी एक वीडियो भेजकर टेस्ट करें! 🚀"
    )

@bot.on_message(filters.command("channel") & filters.private)
async def channel_cmd(c, m):
    """चैनल की जानकारी दिखाएं"""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        member = await bot.get_chat_member(CHANNEL_ID, "me")
        admin_status = "✅ हाँ" if member.status in ["administrator", "creator"] else "❌ नहीं"
        
        await m.reply_text(
            f"📢 **चैनल जानकारी:**\n\n"
            f"📌 **नाम:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"🔗 **लिंक:** {chat.invite_link or 'https://t.me/videoslinkmp4'}\n"
            f"👑 **बॉट एडमिन:** {admin_status}\n\n"
            f"📊 **स्टेटस:** {'✅ कनेक्टेड' if admin_status == '✅ हाँ' else '❌ एडमिन नहीं'}"
        )
    except Exception as e:
        await m.reply_text(f"❌ चैनल कनेक्ट नहीं है: {str(e)}")

@bot.on_message((filters.video | filters.document | filters.audio) & filters.private)
async def handle_media(c, m):
    temp_msg = None
    try:
        # प्रोसेसिंग मैसेज
        temp_msg = await m.reply_text("⏳ लिंक बन रहा है... कृपया प्रतीक्षा करें", quote=True)
        
        # फाइल की जानकारी लॉग करें
        if m.video:
            logger.info(f"Processing video: {m.video.file_name} - {m.video.file_size} bytes")
            file_name = m.video.file_name or "video.mp4"
            file_size = m.video.file_size
            duration = getattr(m.video, 'duration', 0)
        elif m.document:
            logger.info(f"Processing document: {m.document.file_name} - {m.document.file_size} bytes")
            file_name = m.document.file_name or "document.mp4"
            file_size = m.document.file_size
            duration = 0
        else:
            logger.info(f"Processing audio: {m.audio.file_name} - {m.audio.file_size} bytes")
            file_name = m.audio.file_name or "audio.mp3"
            file_size = m.audio.file_size
            duration = getattr(m.audio, 'duration', 0)
        
        # चैनल में मैसेज कॉपी करें
        logger.info(f"Copying to channel {CHANNEL_ID}")
        channel_msg = await m.copy(CHANNEL_ID)
        logger.info(f"✅ Copied! Message ID: {channel_msg.id}")
        
        # बेस URL प्राप्त करें
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://my-ia-bot-la0g.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{channel_msg.id}"
        
        # डायरेक्ट डाउनलोड लिंक भी बनाएं
        download_link = f"{stream_link}?download=1"
        
        # फाइल साइज फॉर्मेट करें
        size_str = format_file_size(file_size)
        
        # ड्यूरेशन फॉर्मेट करें
        duration_str = format_duration(duration) if duration > 0 else "अज्ञात"
        
        # एम्बेड कोड
        embed_code = f'<video src="{stream_link}" controls width="100%" poster=""></video>'
        
        await temp_msg.edit_text(
            f"✅ **आपका लिंक तैयार है!**\n\n"
            f"📹 **फाइल:** `{file_name}`\n"
            f"📦 **साइज:** {size_str}\n"
            f"⏱️ **अवधि:** {duration_str}\n\n"
            f"🔗 **स्ट्रीमिंग लिंक:**\n"
            f"`{stream_link}`\n\n"
            f"📥 **डायरेक्ट डाउनलोड:**\n"
            f"`{download_link}`\n\n"
            f"💻 **एम्बेड कोड:**\n"
            f"`{embed_code}`\n\n"
            f"🌐 **टेस्ट करें:** {stream_link}\n\n"
            f"✨ लिंक पर क्लिक करें - वीडियो चलना चाहिए!"
        )
        
        # लिंक को प्राइवेट तरीके से भी भेजें
        await m.reply_text(
            f"🔗 **त्वरित लिंक:**\n{stream_link}",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in handle_media: {str(e)}", exc_info=True)
        error_msg = str(e).lower()
        
        error_text = "❌ **एरर हुई!**\n\n"
        
        if "chat not found" in error_msg or "identifier" in error_msg:
            error_text += "🔴 **चैनल ID गलत है!**\n"
            error_text += "कृपया चेक करें:\n"
            error_text += "1. CHANNEL_ID = -1003800002652 सही है?\n"
            error_text += "2. बॉट को चैनल में जोड़ा गया है?"
        elif "admin" in error_msg or "privileges" in error_msg or "rights" in error_msg:
            error_text += "🔴 **बॉट एडमिन नहीं है!**\n"
            error_text += "कृपया @videoslinkmp4 चैनल में जाकर बॉट को एडमिन बनाएं।\n\n"
            error_text += "एडमिन बनाने के लिए:\n"
            error_text += "1. चैनल में जाएं\n"
            error_text += "2. Info → Administrators\n"
            error_text += "3. Add Admin → @Filelinkgunerterbot"
        else:
            error_text += f"🔴 **टेक्निकल एरर:**\n`{str(e)}`"
        
        if temp_msg:
            await temp_msg.edit_text(error_text)
        else:
            await m.reply_text(error_text)

def format_file_size(size):
    """फाइल साइज फॉर्मेट करें"""
    if not size:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def format_duration(seconds):
    """ड्यूरेशन फॉर्मेट करें"""
    if not seconds:
        return "0:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

async def main():
    try:
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
        logger.info(f"🌐 Base URL: https://my-ia-bot-la0g.onrender.com")

        # बॉट शुरू करें
        await bot.start()
        
        # बॉट की जानकारी
        me = await bot.get_me()
        logger.info(f"✅ बॉट @{me.username} शुरू हो गया है!")
        
        # चैनल कनेक्शन चेक करें
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            logger.info(f"📢 चैनल मिला: {chat.title}")
            
            # चेक करें कि बॉट एडमिन है या नहीं
            try:
                member = await bot.get_chat_member(CHANNEL_ID, "me")
                if member.status in ["administrator", "creator"]:
                    logger.info("✅ बॉट एडमिन है - सब ठीक है!")
                else:
                    logger.warning("⚠️ बॉट एडमिन नहीं है!")
                    logger.warning("कृपया @videoslinkmp4 चैनल में बॉट को एडमिन बनाएं")
            except Exception as e:
                logger.warning(f"⚠️ एडमिन स्टेटस चेक नहीं हो सकी: {e}")
                
        except Exception as e:
            logger.error(f"❌ चैनल एक्सेस नहीं हो सका: {e}")
            logger.error("कृपया CHANNEL_ID = -1003800002652 वेरिफाई करें")
        
        logger.info("🚀 बॉट तैयार है! अब वीडियो भेजें")
        await idle()
        
    except Exception as e:
        logger.error(f"Main Error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
