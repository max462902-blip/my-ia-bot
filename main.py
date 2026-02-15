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

# --- WEB SERVER WITH COMPLETE FIXES ---
async def home_handler(request):
    return web.Response(
        text="""
        <html>
            <head>
                <title>Video Link Bot</title>
                <style>
                    body { font-family: Arial; text-align: center; padding: 50px; background: #f0f2f5; }
                    .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
                    h1 { color: #0088cc; }
                    .status { color: green; font-size: 20px; margin: 20px 0; }
                    .info { background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎥 Video Link Generator Bot</h1>
                    <div class="status">✅ बॉट ऑनलाइन है!</div>
                    <div class="info">
                        <p>📢 चैनल: @videoslinkmp4</p>
                        <p>🤖 बॉट: @Filelinkgunerterbot</p>
                        <p>🌐 सर्वर: Render.com</p>
                    </div>
                    <p>बॉट को टेलीग्राम पर इस्तेमाल करें और वीडियो भेजें।</p>
                    <p>आपका लिंक इस फॉर्मेट में होगा:</p>
                    <code>https://my-ia-bot-la0g.onrender.com/file/मैसेज_ID</code>
                </div>
            </body>
        </html>
        """,
        content_type="text/html"
    )

async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        logger.info(f"📥 Stream request for file ID: {file_id}")
        
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID - ID must be a number", status=400)
        
        # चैनल से मैसेज लाएं
        try:
            msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        except Exception as e:
            logger.error(f"❌ Failed to get message: {e}")
            return web.Response(text=f"Message not found in channel: {str(e)}", status=404)
        
        if not msg:
            return web.Response(text="Message not found", status=404)
        
        # मीडिया चेक करें - किसी भी प्रकार की मीडिया फाइल को सपोर्ट करें
        file = None
        file_name = "video.mp4"  # डिफ़ॉल्ट नाम
        file_size = 0
        mime_type = "video/mp4"  # डिफ़ॉल्ट MIME type
        
        if msg.video:
            file = msg.video
            file_name = getattr(file, 'file_name', None)
            if not file_name:
                file_name = f"video_{file_id}.mp4"
            file_size = file.file_size
            mime_type = file.mime_type or "video/mp4"
            logger.info(f"🎬 Video found: {file_name}, Size: {file_size}, MIME: {mime_type}")
            
        elif msg.document:
            file = msg.document
            file_name = getattr(file, 'file_name', None)
            if not file_name:
                file_name = f"document_{file_id}.bin"
            file_size = file.file_size
            mime_type = file.mime_type or "application/octet-stream"
            logger.info(f"📄 Document found: {file_name}, Size: {file_size}, MIME: {mime_type}")
            
        elif msg.audio:
            file = msg.audio
            file_name = getattr(file, 'file_name', None)
            if not file_name:
                file_name = f"audio_{file_id}.mp3"
            file_size = file.file_size
            mime_type = file.mime_type or "audio/mpeg"
            logger.info(f"🎵 Audio found: {file_name}, Size: {file_size}, MIME: {mime_type}")
            
        elif msg.photo:
            # फोटो के लिए अलग हैंडलिंग
            file = msg.photo
            file_size = 0  # फोटो का साइज अलग तरीके से निकालना होगा
            file_name = f"photo_{file_id}.jpg"
            mime_type = "image/jpeg"
            logger.info(f"📷 Photo found, Size: {file_size}")
            
        else:
            return web.Response(text="No media found in this message", status=404)
        
        # अगर file_size 0 है तो error return करें
        if file_size == 0 and not msg.photo:
            return web.Response(text="Invalid file size", status=500)
        
        # Content-Type को और बेहतर बनाएं
        content_type = mime_type
        
        # Range header handling for streaming
        range_header = request.headers.get("Range")
        logger.info(f"📊 Range header: {range_header}")
        
        try:
            if range_header and file_size > 0:
                # Parse range header
                match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if match:
                    start = int(match.group(1))
                    end_str = match.group(2)
                    
                    # Validate range
                    if start >= file_size:
                        return web.Response(
                            status=416,
                            headers={"Content-Range": f"bytes */{file_size}"},
                            text="Range Not Satisfiable"
                        )
                    
                    end = int(end_str) if end_str else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    
                    logger.info(f"📤 Serving bytes {start}-{end}/{file_size} (length: {length})")
                    
                    headers = {
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(length),
                        "Content-Type": content_type,
                        "Accept-Ranges": "bytes",
                        "Content-Disposition": f'inline; filename="{file_name}"',
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
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
                    
                    logger.info(f"✅ Successfully streamed {downloaded} bytes")
                    return response
            
            # No range header or range parsing failed - send entire file
            logger.info(f"📤 Serving entire file: {file_size} bytes")
            headers = {
                "Content-Length": str(file_size) if file_size > 0 else "0",
                "Content-Type": content_type,
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'inline; filename="{file_name}"',
                "Cache-Control": "public, max-age=3600",
            }
            
            response = web.StreamResponse(status=200, headers=headers)
            await response.prepare(request)
            
            # Stream entire file
            async for chunk in bot.stream_media(msg):
                await response.write(chunk)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Streaming chunk error: {str(e)}", exc_info=True)
            return web.Response(text=f"Streaming error: {str(e)}", status=500)
        
    except Exception as e:
        logger.error(f"❌ Streaming Error: {str(e)}", exc_info=True)
        return web.Response(text=f"Streaming error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"🎥 **वीडियो लिंक जनरेटर बॉट**\n\n"
        f"मुझे कोई भी वीडियो या फाइल भेजें, मैं आपको Direct Streaming Link दूंगा।\n\n"
        f"📌 **चैनल:** @videoslinkmp4\n"
        f"🤖 **बॉट:** @Filelinkgunerterbot\n\n"
        f"✨ **फीचर्स:**\n"
        f"• डायरेक्ट स्ट्रीमिंग लिंक\n"
        f"• वेबसाइट में एम्बेड कर सकते हैं\n"
        f"• मोबाइल फ्रेंडली\n"
        f"• सभी फॉर्मेट सपोर्ट (MP4, MKV, AVI, etc.)\n\n"
        f"**अभी एक वीडियो भेजकर टेस्ट करें!** 🚀"
    )

@bot.on_message(filters.command("channel") & filters.private)
async def channel_cmd(c, m):
    """चैनल की जानकारी दिखाएं"""
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        try:
            member = await bot.get_chat_member(CHANNEL_ID, "me")
            admin_status = "✅ हाँ" if member.status in ["administrator", "creator"] else "❌ नहीं"
        except:
            admin_status = "❌ जांच नहीं हो सकी"
        
        # चैनल के आखिरी 5 मैसेज चेक करें
        try:
            messages = []
            async for msg in bot.get_chat_history(CHANNEL_ID, limit=5):
                if msg.video or msg.document:
                    messages.append(f"• ID {msg.id}: {'🎬' if msg.video else '📄'}")
            msg_history = "\n".join(messages) if messages else "कोई मीडिया नहीं"
        except:
            msg_history = "हिस्ट्री नहीं देख सकते"
        
        await m.reply_text(
            f"📢 **चैनल जानकारी:**\n\n"
            f"📌 **नाम:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"🔗 **लिंक:** {chat.invite_link or 'https://t.me/videoslinkmp4'}\n"
            f"👑 **बॉट एडमिन:** {admin_status}\n"
            f"📊 **मेम्बर्स:** {getattr(chat, 'members_count', 'अज्ञात')}\n\n"
            f"📋 **हालिया मीडिया:**\n{msg_history}\n\n"
            f"🌐 **बेस URL:** https://my-ia-bot-la0g.onrender.com"
        )
    except Exception as e:
        await m.reply_text(f"❌ चैनल कनेक्ट नहीं है: {str(e)}")

@bot.on_message((filters.video | filters.document | filters.audio | filters.photo) & filters.private)
async def handle_media(c, m):
    temp_msg = None
    try:
        # प्रोसेसिंग मैसेज
        temp_msg = await m.reply_text("⏳ लिंक बन रहा है... कृपया प्रतीक्षा करें", quote=True)
        
        # फाइल की जानकारी लॉग करें
        media_type = "unknown"
        file_name = "media.mp4"
        file_size = 0
        duration = 0
        
        if m.video:
            media_type = "video"
            file_name = m.video.file_name or f"video_{m.id}.mp4"
            file_size = m.video.file_size
            duration = getattr(m.video, 'duration', 0)
            logger.info(f"🎬 Processing video: {file_name} - {file_size} bytes")
            
        elif m.document:
            media_type = "document"
            file_name = m.document.file_name or f"document_{m.id}.bin"
            file_size = m.document.file_size
            logger.info(f"📄 Processing document: {file_name} - {file_size} bytes")
            
        elif m.audio:
            media_type = "audio"
            file_name = m.audio.file_name or f"audio_{m.id}.mp3"
            file_size = m.audio.file_size
            duration = getattr(m.audio, 'duration', 0)
            logger.info(f"🎵 Processing audio: {file_name} - {file_size} bytes")
            
        elif m.photo:
            media_type = "photo"
            file_name = f"photo_{m.id}.jpg"
            file_size = 0  # फोटो का साइज अलग से निकालना होगा
            logger.info(f"📷 Processing photo")
        
        # चैनल में मैसेज कॉपी करें
        logger.info(f"📤 Copying to channel {CHANNEL_ID}")
        channel_msg = await m.copy(CHANNEL_ID)
        logger.info(f"✅ Copied! Message ID: {channel_msg.id}")
        
        # बेस URL प्राप्त करें
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://my-ia-bot-la0g.onrender.com").rstrip('/')
        stream_link = f"{base_url}/file/{channel_msg.id}"
        
        # फाइल साइज फॉर्मेट करें
        size_str = format_file_size(file_size) if file_size > 0 else "अज्ञात"
        
        # ड्यूरेशन फॉर्मेट करें
        duration_str = format_duration(duration) if duration > 0 else "N/A"
        
        # रिस्पॉन्स मैसेज बनाएं
        response_text = (
            f"✅ **आपका लिंक तैयार है!**\n\n"
            f"📹 **फाइल:** `{file_name}`\n"
            f"📦 **साइज:** {size_str}\n"
        )
        
        if duration > 0:
            response_text += f"⏱️ **अवधि:** {duration_str}\n"
        
        response_text += (
            f"\n🔗 **स्ट्रीमिंग लिंक:**\n"
            f"`{stream_link}`\n\n"
            f"🌐 **लिंक खोलें:** {stream_link}\n\n"
            f"💻 **एम्बेड कोड:**\n"
            f"`<video src='{stream_link}' controls width='100%'></video>`\n\n"
            f"📱 **लिंक पर क्लिक करें - वीडियो चलना चाहिए!**"
        )
        
        await temp_msg.edit_text(response_text)
        
        # अलग से एक छोटा मैसेज सिर्फ लिंक के साथ
        await m.reply_text(
            f"🔗 **त्वरित लिंक:**\n{stream_link}",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"❌ Error in handle_media: {str(e)}", exc_info=True)
        
        error_text = "❌ **एरर हुई!**\n\n"
        
        if "chat not found" in str(e).lower():
            error_text += "🔴 **चैनल ID गलत है!**\n"
            error_text += "कृपया चेक करें:\n"
            error_text += "1. CHANNEL_ID = -1003800002652 सही है?\n"
            error_text += "2. बॉट को चैनल में जोड़ा गया है?"
        elif "admin" in str(e).lower() or "privileges" in str(e).lower():
            error_text += "🔴 **बॉट एडमिन नहीं है!**\n"
            error_text += "कृपया @videoslinkmp4 चैनल में जाकर बॉट को एडमिन बनाएं।"
        else:
            error_text += f"🔴 **टेक्निकल एरर:**\n`{str(e)}`"
        
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

def format_duration(seconds):
    """ड्यूरेशन फॉर्मेट करें"""
    if not seconds or seconds <= 0:
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
                    logger.info(f"✅ बॉट एडमिन है - सब ठीक है!")
                    
                    # एक टेस्ट मैसेज भेजें
                    test_msg = await bot.send_message(CHANNEL_ID, "✅ बॉट एक्टिव है!")
                    logger.info(f"✅ Test message sent: {test_msg.id}")
                    
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
        logger.error(f"❌ Main Error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
