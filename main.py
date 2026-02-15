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

# --- SIMPLE DIRECT DOWNLOAD HANDLER ---
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
                <p><a href="/file/38.mp4">टेस्ट लिंक</a></p>
            </body>
        </html>
        """,
        content_type="text/html"
    )

async def download_handler(request):
    try:
        # URL se file ID nikalo
        path = request.match_info.get("id", "")
        file_id = path.replace('.mp4', '')  # .mp4 hatao
        
        logger.info(f"📥 Download request for file ID: {file_id}")
        
        if not file_id or not file_id.isdigit():
            return web.Response(text="Invalid file ID. Use: /file/123.mp4", status=400)
        
        # Channel se message lao
        try:
            msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return web.Response(text="Message not found", status=404)
        
        if not msg:
            return web.Response(text="Message not found", status=404)
        
        # Video check karo
        if not msg.video and not msg.document:
            return web.Response(text="No video in this message", status=404)
        
        # File details
        file = msg.video or msg.document
        file_name = getattr(file, 'file_name', 'video.mp4')
        if not file_name.endswith('.mp4'):
            file_name = 'video.mp4'
        
        file_size = file.file_size
        
        logger.info(f"🎬 Serving: {file_name} ({file_size} bytes)")
        
        # SIMPLE SOLUTION: Force download as attachment
        headers = {
            "Content-Type": "video/mp4",
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        
        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)
        
        # Download from Telegram and send
        chunk_count = 0
        async for chunk in bot.stream_media(msg):
            await response.write(chunk)
            chunk_count += 1
            if chunk_count % 10 == 0:  # Har 10 chunks pe log
                logger.info(f"📤 Sent {chunk_count * 1024 * 1024} bytes...")
        
        logger.info(f"✅ Download complete: {file_name}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=True)
        return web.Response(text=f"Error: {str(e)}", status=500)

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    await m.reply_text(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"🎥 **वीडियो लिंक जनरेटर बॉट**\n\n"
        f"मुझे कोई भी वीडियो भेजें, मैं Direct Download Link दूंगा।\n\n"
        f"📌 **चैनल:** @videoslinkmp4\n"
        f"🔗 **लिंक फॉर्मेट:** `/file/ID.mp4`\n\n"
        f"**अभी एक वीडियो भेजें!** 🚀"
    )

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_media(c, m):
    temp_msg = None
    try:
        temp_msg = await m.reply_text("⏳ लिंक बन रहा है...", quote=True)
        
        # Channel mein copy karo
        channel_msg = await m.copy(CHANNEL_ID)
        logger.info(f"✅ Copied! Message ID: {channel_msg.id}")
        
        # Direct download link
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://my-ia-bot-la0g.onrender.com").rstrip('/')
        download_link = f"{base_url}/file/{channel_msg.id}.mp4"
        
        # File info
        if m.video:
            file_name = m.video.file_name or f"video_{channel_msg.id}.mp4"
            file_size = m.video.file_size
        else:
            file_name = m.document.file_name or f"video_{channel_msg.id}.mp4"
            file_size = m.document.file_size
        
        size_mb = file_size / (1024 * 1024)
        
        await temp_msg.edit_text(
            f"✅ **डाउनलोड लिंक तैयार!**\n\n"
            f"📹 **फाइल:** `{file_name}`\n"
            f"📦 **साइज:** {size_mb:.2f} MB\n\n"
            f"🔗 **लिंक (क्लिक करें):**\n"
            f"`{download_link}`\n\n"
            f"🌐 **खोलें:** {download_link}\n\n"
            f"👉 **लिंक पर क्लिक करें - वीडियो डाउनलोड होगा!**"
        )
        
        # Extra link message
        await m.reply_text(
            f"🔗 **डाउनलोड लिंक:**\n{download_link}",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}", exc_info=True)
        if temp_msg:
            await temp_msg.edit_text(f"❌ एरर: {str(e)}")

async def main():
    try:
        # Web server
        app = web.Application()
        app.router.add_get("/", home_handler)
        app.router.add_get("/file/{id}", download_handler)
        app.router.add_get("/file/{id}.mp4", download_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🌐 Server started on port {PORT}")

        # Bot start
        await bot.start()
        me = await bot.get_me()
        logger.info(f"✅ Bot @{me.username} started!")
        
        # Test channel
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            logger.info(f"📢 Channel: {chat.title}")
            
            # Send test message
            test = await bot.send_message(CHANNEL_ID, "✅ Bot active!")
            logger.info(f"✅ Test message ID: {test.id}")
        except Exception as e:
            logger.error(f"❌ Channel error: {e}")
        
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Main Error: {e}")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
