import os
import asyncio
import requests
import logging
import time
import base64
from pyrogram import Client, filters, idle
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8208753129:AAHxLUPLP4HexecIgPq2Yr1136Hl8kwnc2E")
PORT = int(os.environ.get("PORT", "10000"))

bot = Client("uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- FILE SIZE FORMATTER ---
def format_size(bytes):
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.2f} GB"

# --- DURATION FORMATTER ---
def format_duration(seconds):
    if not seconds:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

# --- GITHUB UPLOAD (PDF के लिए) ---
def upload_to_github(file_path, filename):
    """PDF को GitHub पर upload करेगा"""
    try:
        # GitHub Token - Render पर Environment Variable में डालना होगा
        GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
        GITHUB_REPO = os.environ.get("GITHUB_REPO", "yourusername/yourrepo")  # अपना repo name डालो
        GITHUB_PATH = f"pdfs/{filename}"
        
        if not GITHUB_TOKEN:
            logger.error("GitHub Token not found!")
            return None
        
        # File को base64 में encode करो
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        
        # GitHub API call
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "message": f"Upload {filename} via bot",
            "content": content
        }
        
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            # Raw GitHub URL (सीधा PDF खुलेगा Chrome में)
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PATH}"
            logger.info(f"✅ GitHub upload successful: {raw_url}")
            return raw_url
        else:
            logger.error(f"GitHub upload failed: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"GitHub Error: {e}")
        return None

# --- UPLOAD TO FILEMOON (Video के लिए) ---
def upload_filemoon(file_path, filename):
    try:
        logger.info(f"Uploading to FileMoon: {filename}")
        server_res = requests.get("https://filemoon.sx/api/upload/server", params={"key": "free"})
        if server_res.status_code == 200:
            server_data = server_res.json()
            if server_data.get('result') and server_data['result'].get('server'):
                server_url = server_data['result']['server']
                upload_url = f"https://{server_url}/upload"
                with open(file_path, 'rb') as f:
                    files = {'files[]': (filename, f, 'video/mp4')}
                    data = {'key': 'free'}
                    res = requests.post(upload_url, data=data, files=files)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('files') and data['files'][0].get('url'):
                        file_url = data['files'][0]['url']
                        logger.info(f"✅ FileMoon upload successful: {file_url}")
                        return file_url
    except Exception as e:
        logger.error(f"FileMoon Error: {e}")
    return None

# --- UPLOAD TO CATBOX (Backup) ---
def upload_catbox(file_path):
    try:
        logger.info("Uploading to Catbox...")
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        with open(file_path, 'rb') as f:
            res = requests.post(url, data=data, files={"fileToUpload": f})
        if res.status_code == 200:
            link = res.text.strip()
            logger.info(f"✅ Catbox upload successful: {link}")
            return link
    except Exception as e:
        logger.error(f"Catbox Error: {e}")
    return None

# --- UPLOAD TO GOFILE (Ultimate Backup) ---
def upload_gofile(file_path):
    try:
        logger.info("Uploading to GoFile...")
        server_res = requests.get("https://api.gofile.io/servers")
        if server_res.status_code == 200:
            server_data = server_res.json()
            if server_data.get('data') and server_data['data'].get('servers'):
                server = server_data['data']['servers'][0]['name']
                upload_url = f"https://{server}.gofile.io/uploadFile"
                with open(file_path, 'rb') as f:
                    files = {'file': f}
                    res = requests.post(upload_url, files=files)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('status') == 'ok':
                        file_id = data['data']['fileId']
                        link = f"https://{server}.gofile.io/download/{file_id}"
                        logger.info(f"✅ GoFile upload successful: {link}")
                        return link
    except Exception as e:
        logger.error(f"GoFile Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(
        text="""
        <html>
            <head>
                <title>Uploader Bot</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: 'Segoe UI', Arial; text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
                    .container { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 500px; width: 90%; color: #333; }
                    h1 { color: #667eea; margin-bottom: 20px; }
                    .status { background: #4CAF50; color: white; padding: 15px; border-radius: 10px; margin: 20px 0; }
                    .info { background: #f8f9fa; padding: 20px; border-radius: 15px; margin: 20px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎥 File Uploader Bot</h1>
                    <div class="status">✅ Bot is Online!</div>
                    <div class="info">
                        <p>📢 <strong>Bot:</strong> @Filelinkgunerterbot</p>
                        <p>📁 Video + PDF Uploader</p>
                    </div>
                </div>
            </body>
        </html>
        """,
        content_type="text/html"
    )

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text(
        "👋 **Welcome!**\n\n"
        "मैं फाइल अपलोडर बॉट हूँ:\n\n"
        "🎥 **वीडियो** → Direct MP4 Link\n"
        "📄 **PDF** → GitHub पर Upload (Chrome में खुलेगा)\n"
        "📁 **कोई भी फाइल** → Direct Link\n\n"
        "**अभी एक फाइल भेजो!** 🚀"
    )

@bot.on_message(filters.video & filters.private)
async def handle_video(c, m):
    async with upload_semaphore:
        status = await m.reply_text("⏳ Downloading...", quote=True)
        file_path = None
        try:
            file_name = m.video.file_name or f"video_{m.id}.mp4"
            file_size = m.video.file_size
            duration = m.video.duration
            size_str = format_size(file_size)
            duration_str = format_duration(duration)
            
            await status.edit_text(f"⏳ Downloaded ({size_str})\n📤 Uploading...")
            file_path = await m.download()
            
            await status.edit_text("⏳ Uploading to FileMoon...")
            link = upload_filemoon(file_path, file_name)
            server_used = "FileMoon"
            
            if not link:
                await status.edit_text("🔄 Trying Catbox...")
                link = upload_catbox(file_path)
                server_used = "Catbox"
            
            if not link:
                await status.edit_text("🔄 Trying GoFile...")
                link = upload_gofile(file_path)
                server_used = "GoFile"
            
            if link:
                # बस सीधा लिंक भेजो - कोई extra message नहीं
                await status.edit_text(
                    f"✅ **Video Ready!**\n\n"
                    f"📹 `{file_name}`\n"
                    f"📦 {size_str}  ⏱️ {duration_str}\n\n"
                    f"🔗 `{link}`"
                )
            else:
                await status.edit_text("❌ Upload Failed!")
        except Exception as e:
            logger.error(f"Video Error: {e}")
            await status.edit_text(f"❌ Error: {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

@bot.on_message(filters.document & filters.private)
async def handle_document(c, m):
    async with upload_semaphore:
        status = await m.reply_text("⏳ Downloading...", quote=True)
        file_path = None
        try:
            file_name = m.document.file_name or f"file_{m.id}"
            file_size = m.document.file_size
            mime_type = m.document.mime_type or ""
            size_str = format_size(file_size)
            
            await status.edit_text(f"⏳ Downloaded ({size_str})\n📤 Uploading...")
            file_path = await m.download()
            
            is_pdf = file_name.lower().endswith('.pdf') or 'pdf' in mime_type.lower()
            
            if is_pdf:
                await status.edit_text("⏳ Uploading to GitHub...")
                
                # GitHub पर Upload करो
                github_link = upload_to_github(file_path, file_name)
                
                if github_link:
                    await status.edit_text(
                        f"✅ **PDF Ready!**\n\n"
                        f"📄 `{file_name}`\n"
                        f"📦 {size_str}\n\n"
                        f"🌐 **Chrome में खुलेगा:**\n"
                        f"{github_link}"
                    )
                else:
                    # GitHub fail हो जाए तो Catbox backup
                    await status.edit_text("🔄 GitHub failed, trying Catbox...")
                    link = upload_catbox(file_path)
                    if link:
                        await status.edit_text(
                            f"✅ **PDF Ready!**\n\n"
                            f"📄 `{file_name}`\n"
                            f"📦 {size_str}\n\n"
                            f"🔗 `{link}`"
                        )
                    else:
                        await status.edit_text("❌ Upload Failed!")
            else:
                await status.edit_text("⏳ Uploading to Catbox...")
                link = upload_catbox(file_path)
                if not link:
                    link = upload_gofile(file_path)
                
                if link:
                    await status.edit_text(
                        f"✅ **File Ready!**\n\n"
                        f"📁 `{file_name}`\n"
                        f"📦 {size_str}\n\n"
                        f"🔗 `{link}`"
                    )
                else:
                    await status.edit_text("❌ Upload Failed!")
                    
        except Exception as e:
            logger.error(f"Document Error: {e}")
            await status.edit_text(f"❌ Error: {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

async def main():
    app = web.Application()
    app.router.add_get("/", home)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Web server running on port {PORT}")
    await bot.start()
    me = await bot.get_me()
    logger.info(f"✅ Bot @{me.username} started!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
