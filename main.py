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
PORT = int(os.environ.get("PORT", "10000"))
ADMIN_IDS = [5593666654]  # Apna Telegram ID yaha daalo

bot = Client("uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
upload_semaphore = asyncio.Semaphore(1)

# --- USER DATABASE (Simple JSON) ---
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

# --- UPLOAD TO FILEMOON (BEST FREE HOSTING) ---
def upload_filemoon(file_path, filename):
    """FileMoon par upload karo - 10GB/file, unlimited storage"""
    try:
        url = "https://filemoon.sx/api/upload/server"
        
        # Server lene ke liye API call
        server_res = requests.get("https://filemoon.sx/api/upload/server", params={"key": "free"})
        if server_res.status_code == 200:
            server_url = server_res.json()['result']['server']
            
            # Actual upload
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
        logger.error(f"FileMoon Error: {e}")
    return None

# --- UPLOAD TO GOFILE (Backup) ---
def upload_gofile(file_path):
    """GoFile par upload - unlimited, no account needed"""
    try:
        # Server lene ke liye
        server_res = requests.get("https://api.gofile.io/servers")
        if server_res.status_code == 200:
            server = server_res.json()['data']['servers'][0]['name']
            
            # Upload karo
            upload_url = f"https://{server}.gofile.io/uploadFile"
            with open(file_path, 'rb') as f:
                files = {'file': f}
                res = requests.post(upload_url, files=files)
            
            if res.status_code == 200:
                data = res.json()
                if data['status'] == 'ok':
                    # Direct download link
                    file_id = data['data']['fileId']
                    return f"https://{server}.gofile.io/download/{file_id}/video.mp4"
    except Exception as e:
        logger.error(f"GoFile Error: {e}")
    return None

# --- UPLOAD TO MEDIAFIRE (Ultimate Backup) ---
def upload_mediafire(file_path, filename):
    """MediaFire par upload - 10GB free"""
    try:
        # Simple upload - MediaFire ka API thoda complex hai
        # Isliye abhi ke liye GoFile use karte hain
        return upload_gofile(file_path)
    except Exception as e:
        logger.error(f"MediaFire Error: {e}")
    return None

# --- WEB SERVER ---
async def home(request):
    return web.Response(text="✅ Bot is Running! Total Users: " + str(len(load_users())), content_type="text/html")

async def stats_handler(request):
    """User stats dikhao"""
    users = load_users()
    html = "<html><head><title>Bot Stats</title><style>body{font-family:Arial;padding:20px}</style></head><body>"
    html += f"<h1>📊 Bot Statistics</h1>"
    html += f"<p>Total Users: <b>{len(users)}</b></p>"
    html += f"<p>Total Files Uploaded: <b>{sum(u.get('total_files',0) for u in users.values())}</b></p>"
    html += "<hr>"
    
    for uid, data in sorted(users.items(), key=lambda x: x[1]['last_seen'], reverse=True)[:20]:
        html += f"<div style='border:1px solid #ddd; padding:10px; margin:5px; border-radius:5px;'>"
        html += f"<b>{data.get('first_name')} {data.get('last_name', '')}</b> (@{data.get('username', 'N/A')})<br>"
        html += f"ID: {uid}<br>"
        html += f"Visits: {data.get('visits', 0)} | Files: {data.get('total_files', 0)}<br>"
        html += f"Last Seen: {datetime.fromtimestamp(data.get('last_seen', 0)).strftime('%Y-%m-%d %H:%M:%S')}<br>"
        html += f"DC: {data.get('dc_id', 'N/A')} | Premium: {'✅' if data.get('is_premium') else '❌'}"
        html += "</div>"
    
    html += "</body></html>"
    return web.Response(text=html, content_type="text/html")

# --- BOT HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    user_data = track_user(m.from_user)
    
    # User info message for admin
    admin_msg = (
        f"👤 **New User Started**\n\n"
        f"**ID:** `{m.from_user.id}`\n"
        f"**Name:** {m.from_user.first_name} {m.from_user.last_name or ''}\n"
        f"**Username:** @{m.from_user.username or 'N/A'}\n"
        f"**DC:** {m.from_user.dc_id or 'N/A'}\n"
        f"**Premium:** {'✅' if m.from_user.is_premium else '❌'}\n"
        f"**Language:** {m.from_user.language_code or 'N/A'}\n"
        f"**Visits:** {user_data['visits']}"
    )
    
    # Send to admin
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_msg)
        except:
            pass
    
    # Reply to user
    await m.reply_text(
        f"👋 **नमस्ते {m.from_user.first_name}!**\n\n"
        f"मैं वीडियो अपलोडर बॉट हूँ। मुझे कोई भी वीडियो या फाइल भेजो, "
        f"मैं सीधा **MP4 लिंक** दूंगा जो कभी खत्म नहीं होगा।\n\n"
        f"📤 **फ्री सर्वर:** FileMoon + GoFile\n"
        f"💾 **Limit:** 10GB तक की फाइल\n"
        f"⚡ **Speed:** High Speed CDN\n\n"
        f"**अभी एक वीडियो भेजो!** 🚀"
    )

@bot.on_message(filters.command("stats") & filters.private)
async def stats_cmd(c, m):
    """User ko apni stats dikhao"""
    users = load_users()
    user_data = users.get(str(m.from_user.id), {})
    
    await m.reply_text(
        f"📊 **Your Stats**\n\n"
        f"🆔 **ID:** `{m.from_user.id}`\n"
        f"📁 **Files Uploaded:** {user_data.get('total_files', 0)}\n"
        f"👁️ **Visits:** {user_data.get('visits', 1)}\n"
        f"📅 **First Seen:** {datetime.fromtimestamp(user_data.get('first_seen', 0)).strftime('%Y-%m-%d') if user_data.get('first_seen') else 'Today'}\n"
        f"⚡ **DC:** {m.from_user.dc_id or 'N/A'}\n"
        f"💎 **Premium:** {'✅' if m.from_user.is_premium else '❌'}"
    )

@bot.on_message(filters.command("admin") & filters.private)
async def admin_cmd(c, m):
    """Admin commands"""
    if m.from_user.id not in ADMIN_IDS:
        return
    
    users = load_users()
    total_files = sum(u.get('total_files', 0) for u in users.values())
    
    await m.reply_text(
        f"👑 **Admin Panel**\n\n"
        f"**Total Users:** `{len(users)}`\n"
        f"**Total Files:** `{total_files}`\n"
        f"**Active Users (24h):** `{sum(1 for u in users.values() if u.get('last_seen', 0) > time.time() - 86400)}`\n\n"
        f"Commands:\n"
        f"• /broadcast [message] - सभी users को message भेजो\n"
        f"• /user [id] - किसी user की info देखो"
    )

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(c, m):
    """Broadcast to all users"""
    if m.from_user.id not in ADMIN_IDS:
        return
    
    text = m.text.replace("/broadcast", "").strip()
    if not text:
        await m.reply_text("❌ Message likho: /broadcast Hello everyone!")
        return
    
    users = load_users()
    sent = 0
    failed = 0
    
    status = await m.reply_text(f"📤 Broadcasting to {len(users)} users...")
    
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), text)
            sent += 1
            await asyncio.sleep(0.05)  # Rate limit se bachne ke liye
        except:
            failed += 1
    
    await status.edit_text(f"✅ Broadcast complete!\n\nSent: {sent}\nFailed: {failed}")

@bot.on_message((filters.video | filters.document) & filters.private)
async def handle_upload(c, m):
    async with upload_semaphore:
        # User track karo
        user_data = track_user(m.from_user)
        
        status = await m.reply_text("📥 **Step 1/4:** फाइल डाउनलोड हो रही है...", quote=True)
        file_path = None
        
        try:
            # Get file info
            if m.video:
                file_name = m.video.file_name or f"video_{m.id}.mp4"
                file_size = m.video.file_size
                file_duration = m.video.duration
            else:
                file_name = m.document.file_name or f"file_{m.id}.bin"
                file_size = m.document.file_size
                file_duration = None
            
            # Size format
            size_mb = file_size / (1024 * 1024)
            
            # Download
            file_path = await m.download()
            await status.edit_text(f"📤 **Step 2/4:** फाइल अपलोड हो रही है... ({size_mb:.2f} MB)")
            
            # Try FileMoon first
            link = upload_filemoon(file_path, file_name)
            server_used = "FileMoon"
            
            # If FileMoon fails, try GoFile
            if not link:
                await status.edit_text("🔄 FileMoon busy, GoFile try kar raha hoon...")
                link = upload_gofile(file_path)
                server_used = "GoFile"
            
            if link:
                # Track file
                file_info = {
                    'name': file_name,
                    'size': file_size,
                    'server': server_used,
                    'link': link,
                    'time': time.time()
                }
                track_file(m.from_user.id, file_info)
                
                # Success message
                await status.edit_text(
                    f"✅ **Upload Complete!**\n\n"
                    f"📹 **File:** `{file_name}`\n"
                    f"📦 **Size:** {size_mb:.2f} MB\n"
                    f"⏱️ **Duration:** {file_duration//60}:{file_duration%60:02d} min" if file_duration else ""
                    f"🌐 **Server:** {server_used}\n\n"
                    f"🔗 **Direct MP4 Link:**\n"
                    f"`{link}`\n\n"
                    f"📱 **Click to Play:** {link}\n\n"
                    f"💾 **This link never expires!**"
                )
                
                # Send link separately
                await m.reply_text(
                    f"🔗 **Your MP4 Link:**\n{link}",
                    disable_web_page_preview=True
                )
                
                # Notify admin
                admin_msg = (
                    f"📤 **New Upload**\n\n"
                    f"**User:** {m.from_user.first_name} (@{m.from_user.username})\n"
                    f"**ID:** `{m.from_user.id}`\n"
                    f"**File:** {file_name}\n"
                    f"**Size:** {size_mb:.2f} MB\n"
                    f"**Server:** {server_used}\n"
                    f"**Total Files:** {user_data['total_files'] + 1}"
                )
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, admin_msg)
                    except:
                        pass
                        
            else:
                await status.edit_text(
                    "❌ **Upload Failed!**\n\n"
                    "सभी सर्वर व्यस्त हैं। थोड़ी देर बाद फिर try करो।"
                )
                
        except Exception as e:
            logger.error(f"Error: {e}")
            await status.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

async def main():
    # Web server
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/stats", stats_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"🌐 Web server running on port {PORT}")
    
    # Bot start
    await bot.start()
    me = await bot.get_me()
    logger.info(f"✅ Bot @{me.username} started!")
    
    # Load users
    users = load_users()
    logger.info(f"📊 Total users in DB: {len(users)}")
    
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
