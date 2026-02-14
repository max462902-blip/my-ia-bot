import os
import asyncio
import requests
import logging
from pyrogram import Client, filters

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "") # नया टोकन यहाँ डालें

bot = Client("pixeldrain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# एक बार में सिर्फ 1 फाइल (ताकि 500MB में क्रैश न हो)
upload_semaphore = asyncio.Semaphore(1)

# --- PIXELDRAIN ENGINE ---
def upload_to_pixeldrain(file_path):
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                "https://pixeldrain.com/api/file/",
                files={"file": f}
            )
        
        if response.status_code == 201:
            file_id = response.json()["id"]
            # ऐप के लिए स्पेशल डायरेक्ट लिंक ट्रिक
            return f"https://pixeldrain.com/api/file/{file_id}?filename=course_video.mp4"
        return None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text("नमस्ते! वीडियो भेजें, मैं **App-Compatible Direct MP4 Link** दूँगा।")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        status_msg = await m.reply_text("📥 टेलीग्राम से डाउनलोड हो रहा है...", quote=True)
        file_path = None
        
        try:
            file_path = await m.download()
            
            await status_msg.edit_text("🚀 Pixeldrain पर अपलोड हो रहा है...")
            direct_link = upload_to_pixeldrain(file_path)
            
            if direct_link:
                await status_msg.edit_text(
                    f"✅ **Direct Link Ready!**\n\n"
                    f"🔗 `{direct_link}`\n\n"
                    f"इसे कॉपी करके एडमिन पैनल में लगायें। यह ऐप में सीधा चलेगा।"
                )
            else:
                await status_msg.edit_text("❌ अपलोड फेल हो गया।")

        except Exception as e:
            await status_msg.edit_text(f"❌ एरर: {e}")
        
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path) # फाइल डिलीट ताकि स्टोरेज न भरे

# --- RUN ---
if __name__ == "__main__":
    bot.run()
