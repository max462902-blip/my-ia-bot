import os
import asyncio
import requests
import logging
import time
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
    """फाइल साइज को MB/GB में बदलें"""
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
    """वीडियो की अवधि को MM:SS या HH:MM:SS में बदलें"""
    if not seconds:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

# --- UPLOAD TO FILEMOON (Primary) ---
def upload_filemoon(file_path, filename):
    """FileMoon पर अपलोड करें - 10GB/file, unlimited storage"""
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
    """Catbox.moe पर अपलोड करें - Backup server"""
    try:
        logger.info("Uploading to Catbox (backup)...")
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
    """GoFile पर अपलोड करें - जब सब फेल हो जाए"""
    try:
        logger.info("Uploading to GoFile (ultimate backup)...")
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

# --- PDF UPLOAD HANDLER ---
def upload_pdf(file_path, filename):
    """PDF files के लिए अलग handler"""
    try:
        url = "https://catbox.moe/user/api.php"
        data = {"reqtype": "fileupload", "userhash": ""}
        with open(file_path, 'rb') as f:
            res = requests.post(url, data=data, files={"fileToUpload": f})
        if res.status_code == 200:
            link = res.text.strip()
            logger.info(f"✅ PDF upload successful: {link}")
            return link
    except Exception as e:
        logger.error(f"PDF Upload Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(
        text="""
        <html>
            <head><title>Uploader Bot</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>✅ Bot is Running!</h1>
                <p>Send video or file to @Filelinkgunerterbot</p>
            </body>
        </html>
        """,
        content_type="text/html"
    )

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start(c, m):
    await m.reply_text(
        "👋 **नमस्ते!**\n\n"
        "मैं फाइल अपलोडर बॉट हूँ। मुझे भेजो:\n"
        "🎥 **वीडियो** → MP4 Direct Link मिलेगा\n"
        "📄 **PDF** → Chrome में खुलने वाला PDF Link मिलेगा\n"
        "📁 **कोई भी फाइल** → Download Link मिलेगा\n\n"
        "**अभी एक फाइल भेजो!** 🚀"
    )

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(c, m):
    await m.reply_text(
        "📚 **Help Guide**\n\n"
        "🎥 **Video Upload**\n"
        "• Video भेजो → MP4 Link मिलेगा\n"
        "• Size और Duration भी दिखेगा\n\n"
        "📄 **PDF Upload**\n"
        "• PDF भेजो → Chrome में खुलेगा\n"
        "• Direct PDF Viewer Link\n\n"
        "📁 **Other Files**\n"
        "• कोई भी फाइल भेजो → Download Link\n\n"
        "**Servers Used:**\n"
        "• FileMoon (Primary)\n"
        "• Catbox (Backup)\n"
        "• GoFile (Ultimate Backup)"
    )

@bot.on_message(filters.video & filters.private)
async def handle_video(c, m):
    async with upload_semaphore:
        status = await m.reply_text("⏳ **Step 1/4:** वीडियो डाउनलोड हो रहा है...", quote=True)
        file_path = None
        try:
            file_name = m.video.file_name or f"video_{m.id}.mp4"
            file_size = m.video.file_size
            duration = m.video.duration
            size_str = format_size(file_size)
            duration_str = format_duration(duration)
            await status.edit_text(f"⏳ **Step 2/4:** डाउनलोड पूरा! ({size_str})\n📤 अपलोड शुरू...")
            file_path = await m.download()
            await status.edit_text("⏳ **Step 3/4:** FileMoon पर अपलोड हो रहा है...")
            link = upload_filemoon(file_path, file_name)
            server_used = "FileMoon"
            if not link:
                await status.edit_text("🔄 FileMoon busy, Catbox try कर रहा हूँ...")
                link = upload_catbox(file_path)
                server_used = "Catbox"
            if not link:
                await status.edit_text("🔄 Catbox भी busy, GoFile try कर रहा हूँ...")
                link = upload_gofile(file_path)
                server_used = "GoFile"
            if link:
                await status.edit_text(
                    f"✅ **Video Upload Complete!**\n\n"
                    f"📹 **Filename:** `{file_name}`\n"
                    f"📦 **Size:** `{size_str}`\n"
                    f"⏱️ **Duration:** `{duration_str}`\n"
                    f"🌐 **Server:** `{server_used}`\n\n"
                    f"🔗 **Direct MP4 Link:**\n"
                    f"`{link}`\n\n"
                    f"📱 **Click to Play:** {link}\n\n"
                    f"💾 **This link never expires!**"
                )
                await m.reply_text(f"🔗 **Your Video Link:**\n{link}", disable_web_page_preview=True)
            else:
                await status.edit_text("❌ **Upload Failed!** सभी सर्वर व्यस्त हैं।")
        except Exception as e:
            logger.error(f"Video Error: {e}")
            await status.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

@bot.on_message(filters.document & filters.private)
async def handle_document(c, m):
    async with upload_semaphore:
        status = await m.reply_text("⏳ **Step 1/3:** फाइल डाउनलोड हो रही है...", quote=True)
        file_path = None
        try:
            file_name = m.document.file_name or f"file_{m.id}"
            file_size = m.document.file_size
            mime_type = m.document.mime_type or ""
            size_str = format_size(file_size)
            await status.edit_text(f"⏳ **Step 2/3:** डाउनलोड पूरा! ({size_str})\n📤 अपलोड शुरू...")
            file_path = await m.download()
            is_pdf = file_name.lower().endswith('.pdf') or 'pdf' in mime_type.lower()
            if is_pdf:
                await status.edit_text("⏳ **Step 3/3:** PDF अपलोड हो रहा है...")
                link = upload_pdf(file_path, file_name)
                file_type = "📄 PDF"
                viewer_note = "\n🌐 **Open in Chrome:** यह लिंक Chrome में सीधा खुलेगा"
            else:
                await status.edit_text("⏳ **Step 3/3:** फाइल अपलोड हो रही है...")
                link = upload_catbox(file_path)
                if not link:
                    link = upload_gofile(file_path)
                file_type = "📁 File"
                viewer_note = ""
            if link:
                await status.edit_text(
                    f"✅ **Upload Complete!**\n\n"
                    f"{file_type} **Name:** `{file_name}`\n"
                    f"📦 **Size:** `{size_str}`\n"
                    f"{viewer_note}\n\n"
                    f"🔗 **Direct Link:**\n"
                    f"`{link}`\n\n"
                    f"💾 **This link never expires!**"
                )
                await m.reply_text(f"🔗 **Your Link:**\n{link}", disable_web_page_preview=True)
            else:
                await status.edit_text("❌ **Upload Failed!** सभी सर्वर व्यस्त हैं।")
        except Exception as e:
            logger.error(f"Document Error: {e}")
            await status.edit_text(f"❌ **Error:** {str(e)}")
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
