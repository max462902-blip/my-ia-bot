import os
import asyncio
import requests
import logging
import time
import json
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG ---
API_ID = int(os.environ.get("APP_ID", "3598514"))
API_HASH = os.environ.get("API_HASH", "6a0df17414daf6935f1f0a71b8af1ee0")
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8208753129:AAHxLUPLP4HexecIgPq2Yr1136Hl8kwnc2E")
PORT = int(os.environ.get("PORT", 10000))  # Render ka PORT variable
ADMIN_IDS = [6380236320]  # Apna Telegram ID

# --- BOT CLIENT ---
bot = Client("uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(2)

# --- USER DATABASE ---
USER_DB = "users.json"

def load_users():
    try:
        with open(USER_DB, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USER_DB, 'w') as f:
        json.dump(users, f, indent=2)

def track_user(user):
    users = load_users()
    user_id = str(user.id)
    now = time.time()
    
    if user_id in users:
        users[user_id]['visits'] += 1
        users[user_id]['last_seen'] = now
        users[user_id]['username'] = user.username or "N/A"
        users[user_id]['first_name'] = user.first_name or "N/A"
        users[user_id]['last_name'] = user.last_name or "N/A"
        users[user_id]['dc_id'] = user.dc_id or 0
        users[user_id]['is_premium'] = user.is_premium or False
    else:
        users[user_id] = {
            'id': user.id,
            'username': user.username or "N/A",
            'first_name': user.first_name or "N/A",
            'last_name': user.last_name or "N/A",
            'language_code': user.language_code or "N/A",
            'dc_id': user.dc_id or 0,
            'is_premium': user.is_premium or False,
            'visits': 1,
            'first_seen': now,
            'last_seen': now,
            'total_files': 0,
            'files': []
        }
    save_users(users)
    return users[user_id]

def track_file(user_id, file_info):
    users = load_users()
    user_id = str(user_id)
    if user_id in users:
        users[user_id]['total_files'] += 1
        users[user_id]['files'].append(file_info)
        save_users(users)

# ============= UPLOAD FUNCTIONS =============

def upload_streamtape(file_path, filename):
    """Streamtape - 10GB limit"""
    try:
        # Demo API (actual use ke liye apni credentials lo)
        res = requests.get("https://api.streamtape.com/file/ul", 
                          params={"login": "demo", "key": "demokey"}, 
                          timeout=30)
        if res.status_code == 200:
            data = res.json()
            if data.get('result') and data['result'].get('url'):
                upload_url = data['result']['url']
                
                with open(file_path, 'rb') as f:
                    files = {'file': (filename, f, 'video/mp4')}
                    upload_res = requests.post(upload_url, files=files, timeout=300)
                    
                    if upload_res.status_code == 200:
                        try:
                            result = upload_res.json()
                            if result.get('result') and result['result'].get('url'):
                                return result['result']['url']
                        except:
                            import re
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
            res = requests.post(url, files=files, timeout=300)
        
        if res.status_code == 200:
            import re
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
        server_res = requests.get(url, params={"key": "free"}, timeout=30)
        
        if server_res.status_code == 200:
            server_url = server_res.json()['result']['server']
            upload_url = f"https://{server_url}/upload"
            
            with open(file_path, 'rb') as f:
                files = {'files[]': (filename, f, 'video/mp4')}
                data = {'key': 'free'}
                res = requests.post(upload_url, data=data, files=files, timeout=300)
            
            if res.status_code == 200:
                data = res.json()
                if data.get('files') and data['files'][0].get('url'):
                    return data['files'][0]['url']
    except Exception as e:
        logger.error(f"FileMoon error: {e}")
    return None

def upload_gofile(file_path, filename):
    """GoFile - 100GB limit"""
    try:
        server_res = requests.get("https://api.gofile.io/servers", timeout=30)
        if server_res.status_code == 200:
            server = server_res.json()['data']['servers'][0]['name']
            upload_url = f"https://{server}.gofile.io/uploadFile"
            
            with open(file_path, 'rb') as f:
                files = {'file': f}
                res = requests.post(upload_url, files=files, timeout=300)
            
            if res.status_code == 200:
                data = res.json()
                if data['status'] == 'ok':
                    file_id = data['data']['fileId']
                    return f"https://{server}.gofile.io/download/{file_id}/{filename}"
    except Exception as e:
        logger.error(f"GoFile error: {e}")
    return None

def upload_pixeldrain(file_path, filename):
    """PixelDrain - 1GB limit"""
    try:
        url = "https://pixeldrain.com/api/file"
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'video/mp4')}
            res = requests.post(url, files=files, timeout=300)
        
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

# ============= WEB SERVER HANDLERS =============

async def home_handler(request):
    """Home page"""
    users = load_users()
    total_users = len(users)
    total_files = sum(u.get('total_files', 0) for u in users.values())
    
    html = f"""
    <html>
        <head>
            <title>Video Uploader Bot</title>
            <style>
                body {{ font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                .container {{ background: rgba(255,255,255,0.1); padding: 30px; border-radius: 10px; }}
                h1 {{ font-size: 48px; margin-bottom: 10px; }}
                .stats {{ display: flex; justify-content: center; gap: 30px; margin: 30px 0; }}
                .stat-box {{ background: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px; min-width: 150px; }}
                .stat-number {{ font-size: 36px; font-weight: bold; }}
                .stat-label {{ font-size: 14px; opacity: 0.8; }}
                .status {{ color: #4ade80; font-size: 20px; }}
                a {{ color: white; text-decoration: none; border-bottom: 1px dotted white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎥 Video Uploader Bot</h1>
                <div class="status">✅ BOT IS ONLINE</div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{total_users}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{total_files}</div>
                        <div class="stat-label">Files Uploaded</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">5</div>
                        <div class="stat-label">Active Servers</div>
                    </div>
                </div>
                
                <p>🤖 <b>Bot:</b> @Filelinkgunerterbot</p>
                <p>📢 <b>Channel:</b> @videoslinkmp4</p>
                <p>⚡ <b>Status:</b> Running on port {PORT}</p>
                <p>🔧 <b>Servers:</b> Streamtape, KrakenFiles, FileMoon, GoFile, PixelDrain</p>
            </div>
        </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

async def stats_handler(request):
    """User stats page for admin"""
    users = load_users()
    
    html = """
    <html>
        <head>
            <title>User Statistics</title>
            <style>
                body { font-family: Arial; padding: 20px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
                h1 { color: #333; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #667eea; color: white; }
                tr:hover { background-color: #f5f5f5; }
                .stats { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 User Statistics</h1>
                <div class="stats">
                    <b>Total Users:</b> """ + str(len(users)) + """ | <b>Total Files:</b> """ + str(sum(u.get('total_files', 0) for u in users.values())) + """
                </div>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Username</th>
                        <th>Files</th>
                        <th>Visits</th>
                        <th>Last Seen</th>
                    </tr>
    """
    
    for uid, data in sorted(users.items(), key=lambda x: x[1]['last_seen'], reverse=True)[:20]:
        last_seen = datetime.fromtimestamp(data.get('last_seen', 0)).strftime('%Y-%m-%d %H:%M')
        html += f"""
                    <tr>
                        <td>{uid}</td>
                        <td>{data.get('first_name', 'N/A')}</td>
                        <td>@{data.get('username', 'N/A')}</td>
                        <td>{data.get('total_files', 0)}</td>
                        <td>{data.get('visits', 0)}</td>
                        <td>{last_seen}</td>
                    </tr>
        """
    
    html += """
                </table>
            </div>
        </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")

async def health_handler(request):
    """Health check for Render"""
    return web.Response(text="OK", status=200)

# ============= BOT COMMANDS =============

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    user_data = track_user(m.from_user)
    
    # Admin notification
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, 
                f"👤 **New User**\n\n"
                f"**ID:** `{m.from_user.id}`\n"
                f"**Name:** {m.from_user.first_name}\n"
                f"**Username:** @{m.from_user.username or 'N/A'}\n"
                f"**Visits:** {user_data['visits']}")
        except:
            pass
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel", url="https://t.me/videoslinkmp4"),
         InlineKeyboardButton("🤖 Bot", url="https://t.me/Filelinkgunerterbot")]
    ])
    
    await m.reply_text(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"मैं **मल्टी-सर्वर अपलोडर बॉट** हूँ।\n\n"
        f"📤 **मैं इन 5 सर्वर पर अपलोड करता हूँ:**\n"
        f"• Streamtape (10GB)\n"
        f"• KrakenFiles (4GB)\n"
        f"• FileMoon (10GB)\n"
        f"• GoFile (100GB)\n"
        f"• PixelDrain (1GB)\n\n"
        f"**अभी एक वीडियो भेजो!** 🚀",
        reply_markup=keyboard
    )

@bot.on_message(filters.command("stats") & filters.private)
async def stats_cmd(c, m):
    users = load_users()
    user_data = users.get(str(m.from_user.id), {})
    
    await m.reply_text(
        f"📊 **Your Stats**\n\n"
        f"🆔 **ID:** `{m.from_user.id}`\n"
        f"📁 **Files Uploaded:** {user_data.get('total_files', 0)}\n"
        f"👁️ **Visits:** {user_data.get('visits', 1)}\n"
        f"📅 **First Seen:** {datetime.fromtimestamp(user_data.get('first_seen', 0)).strftime('%Y-%m-%d') if user_data.get('first_seen') else 'Today'}\n"
        f"⚡ **DC:** {m.from_user.dc_id or 'N/A'}"
    )

@bot.on_message(filters.command("admin") & filters.private)
async def admin_cmd(c, m):
    if m.from_user.id not in ADMIN_IDS:
        return
    
    users = load_users()
    total_files = sum(u.get('total_files', 0) for u in users.values())
    active_24h = sum(1 for u in users.values() if u.get('last_seen', 0) > time.time() - 86400)
    
    await m.reply_text(
        f"👑 **Admin Panel**\n\n"
        f"**Total Users:** `{len(users)}`\n"
        f"**Total Files:** `{total_files}`\n"
        f"**Active (24h):** `{active_24h}`\n"
        f"**Servers:** 5 Active\n"
        f"**Port:** `{PORT}`\n\n"
        f"📊 **Web Stats:** https://my-ia-bot-la0g.onrender.com/stats"
    )

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(c, m):
    if m.from_user.id not in ADMIN_IDS:
        return
    
    text = m.text.replace("/broadcast", "").strip()
    if not text:
        await m.reply_text("Usage: /broadcast <message>")
        return
    
    users = load_users()
    sent = 0
    failed = 0
    
    status = await m.reply_text(f"📤 Broadcasting to {len(users)} users...")
    
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), f"📢 **Broadcast Message**\n\n{text}")
            sent += 1
            await asyncio.sleep(0.1)
        except:
            failed += 1
    
    await status.edit_text(f"✅ Broadcast Complete!\n\nSent: {sent}\nFailed: {failed}")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        user_data = track_user(m.from_user)
        
        status = await m.reply_text("📥 **Downloading...**", quote=True)
        file_path = None
        
        try:
            # File info
            if m.video:
                file_name = m.video.file_name or f"video_{m.id}.mp4"
                file_size = m.video.file_size
            else:
                file_name = m.document.file_name or f"file_{m.id}.bin"
                file_size = m.document.file_size
            
            size_mb = file_size / (1024 * 1024)
            
            # Download
            file_path = await m.download()
            await status.edit_text(f"📤 **Uploading...** ({size_mb:.2f} MB)")
            
            # Try each server
            for server in SERVERS:
                if file_size > server['max_size']:
                    continue
                
                await status.edit_text(f"🚀 Trying {server['name']}...")
                
                loop = asyncio.get_event_loop()
                link = await loop.run_in_executor(None, server['func'], file_path, file_name)
                
                if link:
                    # Track file
                    file_info = {
                        'name': file_name,
                        'size': file_size,
                        'server': server['name'],
                        'link': link,
                        'time': time.time()
                    }
                    track_file(m.from_user.id, file_info)
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 Open Link", url=link)],
                        [InlineKeyboardButton("📢 Channel", url="https://t.me/videoslinkmp4")]
                    ])
                    
                    await status.edit_text(
                        f"✅ **Upload Successful!**\n\n"
                        f"📹 **File:** `{file_name}`\n"
                        f"📦 **Size:** {size_mb:.2f} MB\n"
                        f"🌐 **Server:** {server['name']}\n\n"
                        f"🔗 **Link:** `{link}`",
                        reply_markup=keyboard
                    )
                    
                    # Admin notification
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(admin_id,
                                f"📤 **New Upload**\n\n"
                                f"**User:** {m.from_user.first_name}\n"
                                f"**File:** {file_name}\n"
                                f"**Size:** {size_mb:.2f} MB\n"
                                f"**Server:** {server['name']}")
                        except:
                            pass
                    
                    os.remove(file_path)
                    return
                
                await asyncio.sleep(1)
            
            await status.edit_text("❌ **All servers failed!** Try again later.")
            
        except Exception as e:
            await status.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

# ============= MAIN FUNCTION =============

async def main():
    """Main function with proper port binding"""
    try:
        # Create web app
        app = web.Application()
        app.router.add_get("/", home_handler)
        app.router.add_get("/stats", stats_handler)
        app.router.add_get("/health", health_handler)  # For Render health checks
        
        # Setup runner with proper host and port
        runner = web.AppRunner(app)
        await runner.setup()
        
        # ⚠️ IMPORTANT: Bind to 0.0.0.0 and use PORT environment variable
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        
        logger.info(f"🌐 Web server started successfully on port {PORT}")
        logger.info(f"🌐 URL: http://0.0.0.0:{PORT}")
        
        # Start bot
        await bot.start()
        me = await bot.get_me()
        logger.info(f"✅ Bot @{me.username} started successfully!")
        
        # Log stats
        users = load_users()
        logger.info(f"📊 Loaded {len(users)} users from database")
        
        # Run forever
        await idle()
        
    except Exception as e:
        logger.error(f"❌ Main function error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
