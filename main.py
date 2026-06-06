import os
import time
import math
import json
import asyncio
import requests
import yt_dlp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from threading import Thread
from flask import Flask

# --- Flask Server (Render को जगाए रखने के लिए) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Catbox Bot is running on Render!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- Telegram Bot की डिटेल्स ---
BOT_TOKEN = "8881859433:AAEsGoEO7xrkVSw3i2FqTM2YM20n3N85tKE"  
API_ID = 35985614         
API_HASH = "6a0df17414daf6935f1f0a71b8af1ee9" 

bot = Client("CatboxUploaderBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ग्लोबल वेरिएबल्स ---
ADMIN_ID = 7700628753
GLOBAL_PASSWORD = "jitu@123"
PASSWORD_LIMIT = 999999  # डिफ़ॉल्ट लिमिट (Unlimted)
PASSWORD_USED_BY = {}    # जिन लोगों ने पासवर्ड इस्तेमाल किया है उनका डेटा
user_data = {}
admin_state = None  

# --- मैसेज डिलीट करने के लिए (टेम्परेरी) ---
sent_message_map = {} 
recent_admin_messages = [] 

# --- लिमिट (200 MB) ---
MAX_FILE_SIZE = 200 * 1024 * 1024  

# --- Data Persistence ---
DATA_FILE = "bot_config.json"

def save_data():
    try:
        auth_users = {str(uid): info['name'] for uid, info in user_data.items() if info.get('authenticated')}
        with open(DATA_FILE, "w") as f:
            json.dump({
                "GLOBAL_PASSWORD": GLOBAL_PASSWORD,
                "PASSWORD_LIMIT": PASSWORD_LIMIT,
                "PASSWORD_USED_BY": {str(k): v for k, v in PASSWORD_USED_BY.items()},
                "authenticated_users": auth_users
            }, f)
    except Exception as e: pass

def load_data():
    global GLOBAL_PASSWORD, PASSWORD_LIMIT, PASSWORD_USED_BY, user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                GLOBAL_PASSWORD = data.get("GLOBAL_PASSWORD", "jitu@123")
                PASSWORD_LIMIT = data.get("PASSWORD_LIMIT", 999999)
                PASSWORD_USED_BY = {int(k): v for k, v in data.get("PASSWORD_USED_BY", {}).items()}
                
                saved_users = data.get("authenticated_users", {})
                for uid, name in saved_users.items():
                    uid = int(uid)
                    if uid not in user_data:
                        user_data[uid] = {
                            'name': name,
                            'authenticated': True,
                            'step': 'IDLE',
                            'join_date': get_ist_time(),
                            'last_online': get_ist_time(),
                            'total_uploads': 0
                        }
        except Exception as e: pass

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def format_date(dt):
    if isinstance(dt, str): return dt
    return dt.strftime("%d-%b-%Y %I:%M %p")

# --- Catbox Upload Function (401 Error Fixed) ---
def upload_to_catbox(file_path):
    url = "https://catbox.moe/user/api.php"
    data = {"reqtype": "fileupload"}
    # HTTP 401 एरर रोकने के लिए Headers जोड़ना ज़रूरी है
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": f}
            response = requests.post(url, data=data, files=files, headers=headers)
        if response.status_code == 200:
            return response.text.strip()
        else:
            print(f"Catbox Error: HTTP {response.status_code}")
    except Exception as e:
        print(f"Catbox Upload Error: {e}")
    return None

# --- YouTube Download Function (Max 200MB) ---
def download_youtube_video(url):
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
        
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<=200M]/best[filesize<=200M]',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None

def init_user(user_id, message=None):
    if user_id not in user_data:
        name = message.from_user.first_name if message else "Unknown"
        user_data[user_id] = {
            'name': name,
            'authenticated': False if user_id != ADMIN_ID else True, 
            'step': 'PASSWORD' if user_id != ADMIN_ID else 'IDLE',
            'join_date': get_ist_time(),
            'last_online': get_ist_time(),
            'total_uploads': 0
        }
    else:
        user_data[user_id]['last_online'] = get_ist_time()
        if message:
            user_data[user_id]['name'] = message.from_user.first_name

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users"), InlineKeyboardButton("🔑 Change Password", callback_data="admin_pass")],
        [InlineKeyboardButton("📢 Broadcast / Send Msg", callback_data="admin_msg"), InlineKeyboardButton("🗑 Delete Last Broadcast", callback_data="admin_del")]
    ])

# --- Progress Bar ---
async def progress_bar(current, total, msg, start_time, last_update):
    now = time.time()
    if total == 0: total = 1 
    if now - last_update[0] > 3 or current == total:
        last_update[0] = now
        diff = now - start_time
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        eta = round((total - current) / speed) if speed > 0 else 0
        
        current_mb = round(current / (1024 * 1024), 2)
        total_mb = round(total / (1024 * 1024), 2)
        speed_mb = round(speed / (1024 * 1024), 2)
        
        progress_str = "[{0}{1}]".format(''.join(["█" for _ in range(math.floor(percentage / 5))]), ''.join(["░" for _ in range(20 - math.floor(percentage / 5))]))
        eta_str = f"{eta} sec" if eta < 60 else f"{eta//60} min {eta%60} sec"
        
        text = f"📥 **Downloading...**\n\n{progress_str} **{round(percentage, 2)}%**\n📦 **Size:** `{current_mb} MB / {total_mb} MB`\n🚀 **Speed:** `{speed_mb} MB/s`\n⏳ **ETA:** `{eta_str}`"
        try: await msg.edit_text(text)
        except: pass

@bot.on_message(filters.command("admin"))
async def admin_cmd(client, message):
    if message.chat.id == ADMIN_ID:
        global admin_state
        admin_state = None
        await message.reply("👑 **Welcome to Admin Panel**\nChoose an option below:", reply_markup=admin_keyboard())

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.chat.id
    init_user(user_id, message)
    if user_data[user_id]['authenticated']:
        user_data[user_id]['step'] = 'IDLE'
        await message.reply("**✅ Logged in!**\n\n📥 **Send any Video, PDF, or YouTube/Insta Link (Max 200MB).**")
    else:
        user_data[user_id]['step'] = 'PASSWORD'
        await message.reply("👋 **Welcome!**\n🔐 **Enter Password to continue:**")

@bot.on_callback_query(filters.regex("^admin_"))
async def admin_callbacks(client, callback_query: CallbackQuery):
    if callback_query.message.chat.id != ADMIN_ID:
        return
    data = callback_query.data
    global admin_state, recent_admin_messages

    if data == "admin_users":
        total_users = len(user_data)
        text = f"👥 **Total Users:** `{total_users}`\n\n"
        for uid, info in user_data.items():
            if uid == ADMIN_ID: continue
            text += f"👤 **Name:** {info['name']}\n🆔 **ID:** `{uid}`\n📅 **Joined:** {format_date(info['join_date'])}\n🕒 **Last Online:** {format_date(info['last_online'])}\n📤 **Total Uploads:** {info['total_uploads']}\n"
            text += "➖➖➖➖➖➖➖➖\n"
        if len(text) > 4000:
            for x in range(0, len(text), 4000):
                await client.send_message(ADMIN_ID, text[x:x+4000])
        else:
            await callback_query.message.reply(text)

    elif data == "admin_pass":
        admin_state = "AWAIT_NEW_PASSWORD"
        await callback_query.message.reply("🔑 **Please send the NEW PASSWORD and LIMIT.**\n`उदाहरण: 5550 5` (इसका मतलब सिर्फ 5 लोग पासवर्ड यूज़ कर पाएंगे)")

    elif data == "admin_msg":
        admin_state = "AWAIT_BROADCAST"
        await callback_query.message.reply("📢 **Broadcast / Personal Message Mode!**\n\n👉 **सबको भेजने के लिए:** कोई भी Text/Photo भेजें।\n👉 **किसी एक को भेजने के लिए:** ID स्पेस मेसेज लिखें।")
    
    elif data == "admin_del":
        if not recent_admin_messages:
            return await callback_query.message.reply("❌ **No recent messages/broadcasts found to delete.**")
        
        targets = recent_admin_messages.pop()
        deleted_ops = 0
        for uid, mid in targets:
            try:
                await client.delete_messages(uid, mid)
                deleted_ops += 1
            except: pass
        await callback_query.message.reply(f"✅ **Deleted last broadcast from {deleted_ops} users' chats!**")

@bot.on_message(~filters.command(["start", "admin"]))
async def handle_all_messages(client, message):
    user_id = message.chat.id
    init_user(user_id, message)
    step = user_data[user_id].get('step')

    # === Admin Reply to Delete ===
    if message.text == "/delete" and message.reply_to_message and user_id == ADMIN_ID:
        summary_id = message.reply_to_message.id
        if summary_id in sent_message_map:
            targets = sent_message_map[summary_id]
            for uid, mid in targets:
                try: await client.delete_messages(uid, mid)
                except: pass
            await message.reply("✅ **Message successfully deleted!**")
            del sent_message_map[summary_id] 
        return

    # === Admin State Handling ===
    if user_id == ADMIN_ID:
        global admin_state, GLOBAL_PASSWORD, recent_admin_messages, PASSWORD_LIMIT, PASSWORD_USED_BY
        
        if admin_state == "AWAIT_NEW_PASSWORD" and message.text:
            parts = message.text.strip().split()
            GLOBAL_PASSWORD = parts[0]
            PASSWORD_LIMIT = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 999999
            PASSWORD_USED_BY = {} 
            admin_state = None
            save_data()
            await message.reply(f"✅ **Password Changed to:** `{GLOBAL_PASSWORD}`\n👥 **Max Users:** `{PASSWORD_LIMIT}`")
            return

        elif admin_state == "AWAIT_BROADCAST":
            text_to_check = message.text or message.caption
            is_personal = False; target_id = None; content = None
            
            if text_to_check:
                parts = text_to_check.split(" ", 1)
                if len(parts) > 1 and parts[0].isdigit() and len(parts[0]) > 5:
                    is_personal = True; target_id = int(parts[0]); content = parts[1]
                    
            targets = []
            if is_personal:
                try:
                    msg = await client.send_message(target_id, content) if message.text else await message.copy(target_id, caption=content)
                    targets.append((target_id, msg.id))
                    summary = await message.reply(f"✅ **Message sent to `{target_id}`!**\n_Reply with /delete to remove._")
                except: return await message.reply("❌ **Failed to send.**")
            else:
                for uid in user_data:
                    if uid != ADMIN_ID:
                        try:
                            msg = await message.copy(uid)
                            targets.append((uid, msg.id))
                        except: pass
                summary = await message.reply(f"✅ **Broadcast Sent!**\n_Reply with /delete to remove._")
            
            if targets:
                sent_message_map[summary.id] = targets
                recent_admin_messages.append(targets)
            admin_state = None
            return

    # === Normal User Handling ===
    if not user_data[user_id]['authenticated'] and step != 'PASSWORD':
        user_data[user_id]['step'] = 'PASSWORD'
        return await message.reply("🔐 **Session Expired! Please enter password:**")

    if step == 'PASSWORD':
        if message.text == GLOBAL_PASSWORD:
            if user_id not in PASSWORD_USED_BY:
                if len(PASSWORD_USED_BY) >= PASSWORD_LIMIT:
                    return await message.reply("🚫 **Password Limit Reached!**")
                PASSWORD_USED_BY[user_id] = user_data[user_id]['name']
                
            user_data[user_id]['authenticated'] = True
            user_data[user_id]['step'] = 'IDLE'
            save_data()
            await message.reply("**✅ Password Correct!**\n\n📥 **अब आप कोई भी Video, PDF या YouTube/Insta Link भेज सकते हैं (Max 200MB).**")
        else:
            await message.reply("❌ **Wrong Password! Try again.**")

    elif step == 'IDLE':
        # 1. Handle YouTube / Web Links
        if message.text and ("http://" in message.text or "https://" in message.text):
            url = message.text.strip()
            msg = await message.reply("⏳ **Fetching Video Details... (Checking Size)**")
            
            # YouTube download start
            file_path = await asyncio.to_thread(download_youtube_video, url)
            
            if not file_path:
                return await msg.edit_text("❌ **Download Failed!**\nया तो लिंक गलत है, या वीडियो की साइज **200MB से ज्यादा** है।")
                
            await msg.edit_text("📤 **Video Downloaded! Uploading to Catbox...**")
            
            # Upload to Catbox
            catbox_link = await asyncio.to_thread(upload_to_catbox, file_path)
            
            # Delete local file after upload
            if os.path.exists(file_path): os.remove(file_path)
                
            if catbox_link and catbox_link.startswith("http"):
                user_data[user_id]['total_uploads'] += 1
                await msg.edit_text(f"✅ **Upload Successful!**\n\n🔗 **Direct Link:**\n`{catbox_link}`")
            else:
                await msg.edit_text("❌ **Failed to upload to Catbox server.**")

        # 2. Handle Videos and Documents uploaded to Telegram directly
        elif message.video or message.document:
            file_size = message.video.file_size if message.video else message.document.file_size
            
            if file_size > MAX_FILE_SIZE:
                return await message.reply("❌ **File Size Limit Exceeded!**\nकृपया 200MB से छोटी फाइल भेजें।")
                
            msg = await message.reply("⏳ **Downloading File...**")
            start_time = time.time()
            last_update = [start_time]
            
            file_path = await message.download(progress=progress_bar, progress_args=(msg, start_time, last_update))
            
            await msg.edit_text("📤 **Uploading to Catbox...**")
            catbox_link = await asyncio.to_thread(upload_to_catbox, file_path)
            
            if os.path.exists(file_path): os.remove(file_path)
                
            if catbox_link and catbox_link.startswith("http"):
                user_data[user_id]['total_uploads'] += 1
                await msg.edit_text(f"✅ **Upload Successful!**\n\n🔗 **Direct Link:**\n`{catbox_link}`")
            else:
                await msg.edit_text("❌ **Failed to upload to Catbox server.**")

if __name__ == "__main__":
    # Render पर बॉट को चालू रखने के लिए Flask सर्वर स्टार्ट करना ज़रूरी है
    Thread(target=run_server).start()
    load_data() 
    print("Bot is Starting...")
    bot.run()
