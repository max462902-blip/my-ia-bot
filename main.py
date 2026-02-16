import os
import asyncio
import requests
import logging
import time
import re
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8208753129:AAHxLUPLP4HexecIgPq2Yr1136Hl8kwnc2E")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003800002652"))

bot = Client("multi_server_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Semaphore for concurrent uploads
upload_semaphore = asyncio.Semaphore(2)

# ============= UPLOAD FUNCTIONS =============

def upload_streamtape(file_path, filename):
    """Streamtape - 10GB limit, requires login"""
    try:
        # Get upload URL
        res = requests.get("https://api.streamtape.com/file/ul", 
                          params={"login": "demo", "key": "demokey"})  # Demo keys
        if res.status_code == 200:
            data = res.json()
            if data.get('result') and data['result'].get('url'):
                upload_url = data['result']['url']
                
                # Upload file
                with open(file_path, 'rb') as f:
                    files = {'file': (filename, f, 'video/mp4')}
                    upload_res = requests.post(upload_url, files=files)
                    
                    if upload_res.status_code == 200:
                        # Get download link
                        import json
                        try:
                            result = upload_res.json()
                            if result.get('result') and result['result'].get('url'):
                                return result['result']['url']
                        except:
                            # Try regex if JSON fails
                            match = re.search(r'https://streamtape\.com/[^"\' ]+', upload_res.text)
                            if match:
                                return match.group(0)
    except Exception as e:
        logger.error(f"Streamtape error: {e}")
    return None

def upload_krakenfiles(file_path, filename):
    """KrakenFiles - no login needed, 4GB limit"""
    try:
        url = "https://krakenfiles.com/upload"
        with open(file_path, 'rb') as f:
            files = {'files[]': (filename, f, 'video/mp4')}
            res = requests.post(url, files=files)
        
        if res.status_code == 200:
            # Extract download link
            match = re.search(r'https://krakenfiles\.com/view/[a-zA-Z0-9]+', res.text)
            if match:
                return match.group(0)
    except Exception as e:
        logger.error(f"Krakenfiles error: {e}")
    return None

def upload_filemoon(file_path, filename):
    """FileMoon - 10GB limit"""
    try:
        url = "https://filemoon.sx/api/upload/server"
        server_res = requests.get(url, params={"key": "free"})
        
        if server_res.status_code == 200:
            server_url = server_res.json()['result']['server']
            upload_url = f"https://{server_url}/upload"
            
            with open(file_path, 'rb') as f:
                files = {'files[]': (filename, f, 'video/mp4')}
                data = {'key': 'free'}
                res = requests.post(upload_url, data=data, files=files)
            
            if res.status_code == 200:
                data = res.json()
                if data.get('files') and data['files'][0].get('url'):
                    return data['files'][0]['url']
    except Exception as e:
        logger.error(f"FileMoon error: {e}")
    return None

def upload_gofile(file_path, filename):
    """GoFile - 100GB limit, no login"""
    try:
        # Get server
        server_res = requests.get("https://api.gofile.io/servers")
        if server_res.status_code == 200:
            server = server_res.json()['data']['servers'][0]['name']
            upload_url = f"https://{server}.gofile.io/uploadFile"
            
            with open(file_path, 'rb') as f:
                files = {'file': f}
                res = requests.post(upload_url, files=files)
            
            if res.status_code == 200:
                data = res.json()
                if data['status'] == 'ok':
                    file_id = data['data']['fileId']
                    return f"https://{server}.gofile.io/download/{file_id}/{filename}"
    except Exception as e:
        logger.error(f"GoFile error: {e}")
    return None

def upload_pixeldrain(file_path, filename):
    """PixelDrain - 1GB limit, no login"""
    try:
        url = "https://pixeldrain.com/api/file"
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'video/mp4')}
            res = requests.post(url, files=files)
        
        if res.status_code in [200, 201]:
            data = res.json()
            file_id = data.get('id')
            if file_id:
                return f"https://pixeldrain.com/api/file/{file_id}?download"
    except Exception as e:
        logger.error(f"PixelDrain error: {e}")
    return None

# Server list with priorities
SERVERS = [
    {'name': 'Streamtape', 'func': upload_streamtape, 'max_size': 10 * 1024**3},
    {'name': 'KrakenFiles', 'func': upload_krakenfiles, 'max_size': 4 * 1024**3},
    {'name': 'FileMoon', 'func': upload_filemoon, 'max_size': 10 * 1024**3},
    {'name': 'GoFile', 'func': upload_gofile, 'max_size': 100 * 1024**3},
    {'name': 'PixelDrain', 'func': upload_pixeldrain, 'max_size': 1 * 1024**3}
]

# Telegram backup option
async def create_telegram_link(message):
    """Telegram channel link as backup"""
    try:
        channel_msg = await message.copy(CHANNEL_ID)
        if message.chat.username:
            return f"https://t.me/{message.chat.username}/{channel_msg.id}"
        else:
            channel_short = str(CHANNEL_ID)[4:] if str(CHANNEL_ID).startswith('-100') else str(CHANNEL_ID)
            return f"https://t.me/c/{channel_short}/{channel_msg.id}"
    except:
        return None

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **Multi-Server Upload Bot**\n\n"
        "मैं 5 अलग-अलग सर्वर पर अपलोड करता हूँ:\n"
        "• Streamtape (10GB)\n"
        "• KrakenFiles (4GB)\n"
        "• FileMoon (10GB)\n"
        "• GoFile (100GB)\n"
        "• PixelDrain (1GB)\n\n"
        "कोई भी वीडियो भेजो, मैं सबसे तेज सर्वर पर अपलोड करूंगा।"
    )

@bot.on_message(filters.video & filters.private)
async def handle_video(client, message):
    async with upload_semaphore:
        status = await message.reply_text("📥 Downloading...")
        file_path = None
        
        try:
            # Download file
            file_path = await message.download()
            filename = message.video.file_name or f"video_{message.id}.mp4"
            file_size = message.video.file_size
            
            # Try each server
            for server in SERVERS:
                # Check size limit
                if file_size > server['max_size']:
                    continue
                
                await status.edit_text(f"🚀 Uploading to {server['name']}...")
                
                # Run upload in thread pool
                loop = asyncio.get_event_loop()
                link = await loop.run_in_executor(None, server['func'], file_path, filename)
                
                if link:
                    await status.edit_text(
                        f"✅ **Upload Successful!**\n\n"
                        f"📹 **File:** {filename}\n"
                        f"📦 **Size:** {file_size / (1024**2):.2f} MB\n"
                        f"🌐 **Server:** {server['name']}\n\n"
                        f"🔗 **Link:**\n`{link}`"
                    )
                    
                    # Send link separately
                    await message.reply_text(
                        f"🔗 **Direct Link:**\n{link}",
                        disable_web_page_preview=True
                    )
                    
                    os.remove(file_path)
                    return
                
                # Wait between attempts
                await asyncio.sleep(2)
            
            # If all servers fail, try Telegram backup
            await status.edit_text("🔄 All servers busy, trying Telegram backup...")
            telegram_link = await create_telegram_link(message)
            
            if telegram_link:
                await status.edit_text(
                    f"✅ **Telegram Link Created!**\n\n"
                    f"🔗 `{telegram_link}`\n\n"
                    f"📌 यह लिंक Telegram के सर्वर से चलेगा।"
                )
            else:
                await status.edit_text(
                    "❌ **All servers failed!**\n\n"
                    "सभी 6 सर्वर व्यस्त हैं। थोड़ी देर बाद try करो।"
                )
            
        except Exception as e:
            await status.edit_text(f"❌ Error: {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    bot.run()
