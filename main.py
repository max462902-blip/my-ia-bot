import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web
from pyrogram.errors import FloodWait

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- STREAMING ENGINE (Very Important) ---
async def file_stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        # टेलीग्राम से मैसेज ढूँढना
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))
        
        if not msg.video and not msg.document:
            return web.Response(text="File not found!", status=404)

        file = msg.video or msg.document
        
        # चंकिंग (Chunking) लॉजिक - ताकि बड़ी वीडियो भी चले
        async def stream_generator():
            async for chunk in bot.iter_download(file.file_id):
                yield chunk

        response = web.StreamResponse()
        response.content_type = file.mime_type or "video/mp4"
        response.content_length = file.file_size
        
        await response.prepare(request)
        async for chunk in bot.iter_download(file.file_id):
            await response.write(chunk)
        return response

    except Exception as e:
        return web.Response(text=f"Error: {e}", status=500)

async def home_handler(request):
    return web.Response(text="✅ Bot is Running! Streaming Engine is Active.", content_type="text/html")

async def start_server():
    app = web.Application()
    app.router.add_get("/", home_handler)
    app.router.add_get("/file/{id}", file_stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- BOT COMMANDS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे अपने चैनल से कोई भी वीडियो फॉरवर्ड करें, मैं आपको **Direct MP4 Link** दे दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def get_link(c, m):
    try:
        log_msg = await m.copy(CHANNEL_ID)
        # Render का URL यहाँ इस्तेमाल होगा
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        stream_link = f"{base_url}/file/{log_msg.id}"
        
        await m.reply_text(
            f"✅ **Link Generated!**\n\n"
            f"🔗 **MP4 Link:** `{stream_link}`\n\n"
            f"इसे अपने ऐप के एडमिन पैनल में लगायें।"
        )
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}\nसुनिश्चित करें कि बॉट चैनल में Admin है।")

# --- START EVERYTHING ---
async def main():
    await start_server()
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
