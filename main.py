import os
import time
import uuid
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from internetarchive import upload
from dotenv import load_dotenv

load_dotenv()

# Config (Inhe Render ke Environment Variables mein bharna)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
IA_ACCESS_KEY = os.getenv("IA_ACCESS_KEY")
IA_SECRET_KEY = os.getenv("IA_SECRET_KEY")

bot = Client("archive_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 Hi! Main bade files (400MB+) Archive.org pe upload kar sakta hoon.\n\n"
        "Bas mujhe Video ya PDF bhejo, main aapko Direct Link dunga."
    )

@bot.on_message(filters.video | filters.document)
async def handle_upload(client, message):
    media = message.video or message.document
    
    # Check if it's PDF or Video
    file_name = getattr(media, "file_name", "unknown_file")
    file_size = get_readable_size(media.file_size)
    duration = getattr(media, "duration", 0) # Sirf video ke liye
    
    status = await message.reply_text(f"📥 **Downloading...**\n`{file_name}`\nSize: {file_size}")

    # Local Path
    local_path = f"./downloads/{uuid.uuid4().hex}_{file_name}"
    
    try:
        # 1. Download File
        path = await message.download(file_name=local_path)
        
        await status.edit(f"📤 **Uploading to Archive.org...**\nSize: {file_size}")

        # 2. Archive.org Upload Logic
        identifier = f"bot_up_{uuid.uuid4().hex[:10]}"
        
        # MetaData
        meta = {
            'mediatype': 'movies' if message.video else 'texts',
            'title': file_name,
            'description': f'Uploaded by Telegram Bot. Original Size: {file_size}'
        }

        upload(
            identifier,
            files=[path],
            access_key=IA_ACCESS_KEY,
            secret_key=IA_SECRET_KEY,
            metadata=meta
        )

        # 3. Links Generate Karna
        # Archive.org ka direct download link structure: https://archive.org/download/IDENTIFIER/FILENAME
        encoded_file_name = file_name.replace(" ", "%20")
        direct_link = f"https://archive.org/download/{identifier}/{encoded_file_name}"
        viewer_link = f"https://archive.org/details/{identifier}"

        # 4. Success Message
        response = (
            f"✅ **Upload Complete!**\n\n"
            f"📄 **File:** `{file_name}`\n"
            f"📦 **Size:** {file_size}\n"
        )
        
        if message.video:
            response += f"⏳ **Duration:** {duration} seconds\n"
            btn_text = "🎬 Watch/Stream Video"
        else:
            btn_text = "📖 Open PDF in Chrome"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_text, url=direct_link)],
            [InlineKeyboardButton("🔗 Archive Page", url=viewer_link)]
        ])

        await status.delete()
        await message.reply_text(response, reply_markup=reply_markup)

    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}")
    
    finally:
        # 5. Disk se delete karna
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    bot.run()
