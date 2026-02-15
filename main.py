import os
import asyncio
import logging
from aiohttp import web
from pyrogram import Client, filters

# --- LOGGING (गलती पकड़ने के लिए) ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- जरूरी डेटा (Render के Environment Variables से लेगा) ---
API_ID = int(os.environ.get("APP_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
# Render खुद यह URL देगा
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip('/')
PORT = int(os.environ.get("PORT", 10000))

# --- Bot शुरू करो ---
bot = Client(
    "my_webhook_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- 1. Webhook Handler (यहाँ से Telegram messages आएंगे) ---
async def webhook_handler(request):
    try:
        # 1. आया हुआ JSON data पढ़ो
        update_data = await request.json()
        logger.info(f"Update received via webhook: {update_data}")
        
        # 2. यह Data Pyrogram के समझने लायक है
        update = await bot.process_update(update_data)
        
        # 3. Telegram को बताओ कि सब ठीक रहा
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

# --- 2. Web Server और Route सेट करो ---
async def home(request):
    return web.Response(text="✅ Bot is Running with Webhook!")

async def health_check(request):
    """Render के लिए Health Check"""
    return web.Response(text="OK")

# --- 3. बॉट के COMMANDS (तुम्हारे पुराने वैसे ही) ---
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    logger.info(f"Start command from {message.from_user.id}")
    await message.reply_text(
        "✅ **Bot is Working with Webhook!**\n\n"
        "Send me any video."
    )

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_media(client, message):
    try:
        status_msg = await message.reply_text("⏳ Processing...")
        # Channel में forward करो
        forwarded = await message.copy(CHANNEL_ID)
        # Stream link बनाओ
        stream_link = f"{BASE_URL}/stream/{forwarded.id}"
        await status_msg.delete()
        await message.reply_text(f"✅ **Stream Link:**\n\n`{stream_link}`")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

# --- 4. Stream Handler (पुराना वैसे ही) ---
async def stream_handler(request):
    try:
        file_id = request.match_info.get("id")
        msg = await bot.get_messages(CHANNEL_ID, int(file_id))

        if not msg or (not msg.video and not msg.document):
            return web.Response(text="File not found!", status=404)

        file = msg.video or msg.document
        file_size = file.file_size
        mime_type = file.mime_type or "video/mp4"

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }

        response = web.StreamResponse(status=200, headers=headers)
        await response.prepare(request)

        async for chunk in bot.stream_media(msg):
            await response.write(chunk)

        return response
    except Exception as e:
        logger.error(f"Stream Error: {e}")
        return web.Response(text="Error occurred", status=500)

# --- 5. MAIN Function (Webhook सेट करना जरूरी है) ---
async def main():
    # Web app तैयार करो
    app = web.Application()
    app.router.add_post(f"/webhook", webhook_handler)  # POST request यहाँ आएगा
    app.router.add_get("/", home)
    app.router.add_get("/health", health_check)
    app.router.add_get("/stream/{id}", stream_handler)

    # Web server शुरू करो
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Web server running on port {PORT}")

    # Bot शुरू करो
    await bot.start()
    me = await bot.get_me()
    logger.info(f"🤖 Bot started: @{me.username}")

    # Webhook URL बनाओ (Render का URL + /webhook)
    webhook_url = f"{BASE_URL}/webhook"
    logger.info(f"Setting webhook to: {webhook_url}")

    # पुराना webhook हटाओ और नया सेट करो
    await bot.delete_webhook()
    await bot.set_webhook(url=webhook_url)

    logger.info("✅ Webhook set successfully! Bot is ready.")
    
    # Render को Health Check के लिए /health चाहिए
    # Bot अब बस इंतज़ार करेगा
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
