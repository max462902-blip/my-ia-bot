import os
import asyncio
from pyrogram import Client, filters
from aiohttp import web

# --- CONFIGURATION ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- WEB SERVER FOR STREAMING ---
async def stream_handler(request):
    return web.Response(text="Bot is Live! Streaming engine active.", content_type="text/html")

async def start_server():
    app = web.Application()
    app.router.add_get("/", stream_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- BOT LOGIC ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text(f"नमस्ते {m.from_user.first_name}!\n\nमुझे अपने चैनल से कोई भी वीडियो फॉरवर्ड करें, मैं आपको **Direct MP4 Link** दे दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def get_link(c, m):
    # फाइल को चैनल में कॉपी करें ताकि परमानेंट लिंक रहे
    try:
        log_msg = await m.copy(CHANNEL_ID)
        # लिंक जनरेट करें (यहाँ Render का URL डालना होगा)
        base_url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        stream_link = f"{base_url}/file/{log_msg.id}"
        
        await m.reply_text(
            f"✅ **Link Generated!**\n\n"
            f"🔗 **MP4 Link:** `{stream_link}`\n\n"
            f"इसे अपने ऐप के एडमिन पैनल में लगायें।"
        )
    except Exception as e:
        await m.reply_text(f"❌ एरर: {e}\nसुनिश्चित करें कि बॉट चैनल में Admin है।")

# --- RUN EVERYTHING ---
async def main():
    print("Starting Web Server...")
    await start_server()
    print("Starting Bot...")
    await bot.start()
    print("Bot is Running..!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
