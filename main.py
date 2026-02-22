import os
import uuid
import threading
import logging
import asyncio
import time
import re
import random
from datetime import datetime
from flask import Flask, redirect
from pyrogram import Client, filters, idle, enums
from huggingface_hub import HfApi
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.WARNING)

# --- SERVER KEEPER ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "Bot is Running!"

@app.route('/file/<path:filename>')
def file_redirect(filename):
    hf_repo = os.environ.get("HF_REPO")
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}?download=true"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- QUEUE SYSTEM ---
upload_queue = asyncio.Queue()
user_batches = {}
user_queue_numbers = {}

# --- CLIENTS ---
bot = Client("main_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=4)
userbot = Client("user_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, workers=4) if SESSION_STRING else None

def get_readable_size(size):
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024: return f"{size:.2f} {unit}"
            size /= 1024
    except:
        return "Unknown"

# ==========================================
#  ⬇️ WORKER (FILE LINK GENERATOR) ⬇️
# ==========================================
# ... (Keep the worker_processor function exactly as it was in your code) ...
async def worker_processor():
    print("👷 Worker started...")
    while True:
        task = await upload_queue.get()
        client, message, media, media_type, original_msg, queue_msg = task
        user_id = message.chat.id
        
        local_path = None
        status_msg = None
        
        try:
            if queue_msg:
                try: await queue_msg.delete()
                except: pass

            original_display_name = None
            if hasattr(media, "file_name") and media.file_name:
                original_display_name = media.file_name
            
            if not original_display_name:
                caption = message.caption or (original_msg.caption if original_msg else "")
                if caption:
                    clean_cap = re.sub(r'[\\/*?:"<>|]', "", caption.split('\n')[0])[:60]
                    ext = ".mp4" if media_type == "video" else ".pdf"
                    if media_type == "photo": ext = ".jpg"
                    original_display_name = f"{clean_cap}{ext}"
            
            if not original_display_name:
                original_display_name = f"File_{int(time.time())}.{media_type}"

            unique_id = uuid.uuid4().hex[:6]
            ext = os.path.splitext(original_display_name)[1]
            if not ext: 
                if media_type == "video": ext = ".mp4"
                elif media_type == "photo": ext = ".jpg"
                else: ext = ".pdf"
            
            final_filename = f"file_{unique_id}{ext}"

            status_msg = await message.reply_text(f"⏳ **Processing:**\n`{original_display_name}`")
            
            if not os.path.exists("downloads"): os.makedirs("downloads")
            local_path = f"downloads/{final_filename}"
            
            await status_msg.edit(f"⬇️ **Downloading...**\n`{original_display_name}`")
            
            if original_msg:
                await original_msg.download(file_name=local_path)
            else:
                await message.download(file_name=local_path)

            file_size = get_readable_size(os.path.getsize(local_path))

            await status_msg.edit(f"⬆️ **Uploading...**\n`{original_display_name}`")
            api = HfApi(token=HF_TOKEN)
            
            await asyncio.to_thread(
                api.upload_file,
                path_or_fileobj=local_path,
                path_in_repo=final_filename,
                repo_id=HF_REPO,
                repo_type="dataset"
            )

            final_link = f"{SITE_URL}/file/{final_filename}"
            
            if user_id not in user_batches: user_batches[user_id] = []
            user_batches[user_id].append({
                "display_name": original_display_name,
                "link": final_link,
                "size": file_size
            })

            await status_msg.delete()

        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {str(e)}")
            logging.error(f"Error: {e}")
        
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            upload_queue.task_done()

        if upload_queue.empty():
            await asyncio.sleep(2)
            if upload_queue.empty() and user_id in user_batches and user_batches[user_id]:
                data = user_batches[user_id]
                final_text = f"✅ **BATCH COMPLETED ({len(data)} Files)**\n\n"
                for item in data:
                    final_text += f"📂 **{item['display_name']}**\n"
                    final_text += f"`{item['link']}`\n"
                    final_text += f"📦 {item['size']}\n\n"
                final_text += "⚡ **Process Finished!**"
                try:
                    if len(final_text) > 4000:
                        parts = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                        for part in parts: await client.send_message(user_id, part)
                    else:
                        await client.send_message(user_id, final_text)
                except: pass
                del user_batches[user_id]
                if user_id in user_queue_numbers: del user_queue_numbers[user_id]

# ==========================================
#  ⬇️ 🔥 ALL PRANK COMMANDS (USERBOT) 🔥 ⬇️
# ==========================================

if userbot:

    # 1. TOKEN EFFECT (.tokon)
    @userbot.on_message(filters.command("tokon", prefixes=".") & filters.me)
    async def break_text(client, message):
        try:
            if len(message.command) < 2: text = "BROKEN"
            else: text = message.text.split(maxsplit=1)[1]
            end_time = time.time() + 60
            while time.time() < end_time:
                await message.edit(f"**{text}**")
                await asyncio.sleep(0.8)
                spaced = " ".join(list(text))
                await message.edit(f"**{spaced}**")
                await asyncio.sleep(0.5)
                falling = "\n".join(list(text))
                await message.edit(f"**{falling}**")
                await asyncio.sleep(1)
                crashed = ""
                for char in text:
                    crashed += char + (" " * random.randint(1, 4))
                await message.edit(f"`{crashed}`")
                await asyncio.sleep(0.5)
            await message.edit(f"✅ **{text}**")
        except: pass

    # 2. HACKER SEQUENCE (.hack)
    @userbot.on_message(filters.command("hack", prefixes=".") & filters.me)
    async def complex_hack(client, message):
        try:
            await message.edit("💻 **CONNECTING TO SERVER...**")
            await asyncio.sleep(1)
            await message.edit("📥 **STEALING DATA...** [45%]")
            await asyncio.sleep(1)
            await message.edit("📥 **STEALING DATA...** [100%]")
            await asyncio.sleep(1)
            for i in range(5, 0, -1):
                await message.edit(f"💣 **DESTRUCTION IN {i}...** 💣")
                await asyncio.sleep(1)
            await message.edit("💥 **BOOM!** 💥")
            await asyncio.sleep(1)
            await message.edit("😈 **YOU ARE HACKED** 😈")
        except: pass

    # 3. GLITCH (3 Minutes Duration, Blink Effect)
    @userbot.on_message(filters.command("glitch", prefixes=".") & filters.me)
    async def glitch_text(client, message):
        try:
            if len(message.command) < 2:
                original_text = "ERROR 404"
            else:
                original_text = message.text.split(maxsplit=1)[1]
            
            # "Invisible Character" (Ye space jaisa hai par khali dikhta hai)
            invisible_text = "ㅤ" 
            
            # 3 Minutes = 180 Seconds
            # Loop delay = 1.5s show + 0.5s hide = 2s approx
            # 180 / 2 = 90 loops
            
            end_time = time.time() + 180 # 3 minute baad rukega
            
            while time.time() < end_time:
                # Show Text (Bold mein)
                await message.edit(f"**{original_text}**")
                await asyncio.sleep(1.5) # 1.5 second dikhega
                
                # Hide Text (Gayab)
                await message.edit(invisible_text)
                await asyncio.sleep(0.5) # 0.5 second gayab rahega
            
            # Last mein text wapis aa jayega
            await message.edit(f"**{original_text}**")
            
        except Exception as e:
            print(f"Glitch Error: {e}")


    
    # ✈️ 3. AIRPLANE DROP (.air <text>)
    @userbot.on_message(filters.command("air", prefixes=".") & filters.me)
    async def airplane_drop(client, message):
        if not PRANK_ACTIVE: return
        try:
            if len(message.command) < 2: text = "BOOM"
            else: text = message.text.split(maxsplit=1)[1]
            
            # Animation Frames
            await message.edit("☁️ . . . . . . . . . .")
            await asyncio.sleep(0.5)
            await message.edit("☁️ ✈️ . . . . . . . .") # Plane Enter
            await asyncio.sleep(0.5)
            await message.edit("☁️ . . ✈️ . . . . . .")
            await asyncio.sleep(0.5)
            await message.edit("☁️ . . . . ✈️ 🪂 . . .") # Drop Parachute
            await asyncio.sleep(0.5)
            await message.edit("☁️ . . . . . . ✈️ . 📦") # Plane Leave
            await asyncio.sleep(0.5)
            await message.edit(f"⬇️\n\n📦") # Box Falling
            await asyncio.sleep(0.5)
            await message.edit(f"💥 **DELIVERY RECEIVED:**\n\n**{text}**") # Reveal
        except: pass
        
# ----------------------------------------------------
    #  MODIFIED: SCAN (REAL BIO + PHOTO + PRANK STATS)
    # ----------------------------------------------------
    @userbot.on_message(filters.command("scan", prefixes=".") & filters.me)
    async def scan_user(client, message):
        if not message.reply_to_message:
            await message.edit("❌ **Reply to a user!**")
            return

        try:
            target = message.reply_to_message.from_user
            target_msg = message.reply_to_message.text or "[Media/Sticker]"
            
            # --- ANIMATION ---
            await message.edit("🔍 **INITIALIZING SCAN...**")
            await asyncio.sleep(1)
            await message.edit("📡 **FETCHING DATABASE RECORDS...**")
            await asyncio.sleep(1)
            await message.edit("🔐 **BYPASSING SECURITY PROTOCOLS...**")
            await asyncio.sleep(1)

            # --- REAL DATA FETCHING ---
            # Bio nikalne ke liye full chat details chahiye
            try:
                full_user = await client.get_chat(target.id)
                bio = full_user.bio if full_user.bio else "No Bio Set"
            except:
                bio = "Hidden/Private"

            name = target.first_name
            last_name = target.last_name if target.last_name else ""
            full_name = f"{name} {last_name}".strip()
            user_id = target.id
            username = f"@{target.username}" if target.username else "No Username"
            
            # --- PRANK DATA (Activity Stats) ---
            # Note: Phone Model/Battery hata diya hai jaisa tune bola
            
            # 1. Fake Phone Number (Masked)
            fake_phone = "xxxxxxxxxx"
            
            # 2. Activity Stats
            total_msgs = random.randint(35, 5000)
            topics = ["Love", "Paisa", "Settings", "Daru", "Admin", "Hacking", "Dhoka", "Notes", "Assignment"]
            fav_topic = random.choice(topics)
            online_count = random.randint(5, 150)
            left_count = random.randint(0, 10)
            
            # 3. Time
            now = datetime.now()
            day = now.strftime("%A")
            time_str = now.strftime("%H:%M:%S")
            
            report = f"""
☠️ **USER REPORT DETECTED** ☠️

👤 **IDENTITY:**
• Name: {full_name}
• ID: `{user_id}`
• User: {username}
• Bio: `{bio}`
• Phone: `{fake_phone}` 🔒
• Location: 🚫 **NOT ALLOWED**

📊 **GROUP ACTIVITY:**
• Total Messages: `{total_msgs}`
• Latest Msg: "{target_msg[:20]}..."
• Favorite Topic: **{fav_topic}**
• Came Online: `{online_count}` times
• Group Left: `{left_count}` times

🕒 **LAST ACTIVE:**
• Day: {day}
• Time: {time_str} (Live)

⚠️ **STATUS:** **SUSPICIOUS ACTIVITY FOUND**
"""
            
            # --- PHOTO HANDLING ---
            # Check karte hain DP hai ya nahi
            photos = []
            async for photo in client.get_chat_photos(target.id, limit=1):
                photos.append(photo)

            if photos:
                # Agar DP hai: Purana text delete karo aur Photo bhejo
                await message.delete()
                await client.send_photo(
                    message.chat.id,
                    photo=photos[0].file_id,
                    caption=report,
                    reply_to_message_id=message.reply_to_message.id # Original bande ko tag karega
                )
            else:
                # Agar DP nahi hai: Sirf Text edit karo
                await message.edit(report)
            
        except Exception as e:
            await message.edit(f"❌ Error: {e}")
    # ----------------------------------------------------

    # 4. TYPING EFFECT (.type)
    @userbot.on_message(filters.command("type", prefixes=".") & filters.me)
    async def type_text(client, message):
        try:
            if len(message.command) < 2: return
            text = message.text.split(maxsplit=1)[1]
            t = ""
            for char in text:
                t += char
                try:
                    await message.edit(f"`{t}█`")
                    await asyncio.sleep(0.2)
                except: pass
            await message.edit(f"**{t}**")
        except: pass

    # 6. KAAL STYLES (.kaal)
    @userbot.on_message(filters.command("kaal", prefixes=".") & filters.me)
    async def kaal_mode(client, message):
        try:
            if len(message.command) < 2: text = "KAAL SHADOW"
            else: text = message.text.split(maxsplit=1)[1]
            
            await message.edit("☠️ **KAAL** ☠️")
            await asyncio.sleep(1)
            styles = [
                f"**{text}**", f"___{text}___", f"`{text}`", 
                f"||{text}||", f"~~{text}~~", f"[{text}]", f"🔥 {text} 🔥"
            ]
            for style in styles:
                await message.edit(style)
                await asyncio.sleep(0.8)
            await message.edit(f"👑 **{text}** 👑")
        except: pass

    # 8. SELF DESTRUCT (.run)
    @userbot.on_message(filters.command("run", prefixes=".") & filters.me)
    async def self_destruct(client, message):
        await message.edit("💣 **Deleting in 5s...**")
        for i in range(5, 0, -1):
            await message.edit(f"💣 **{i}**")
            await asyncio.sleep(1)
        await message.edit("💥")
        await asyncio.sleep(0.5)
        await message.delete()

    # 9. VIRUS (.virus)
    @userbot.on_message(filters.command("virus", prefixes=".") & filters.me)
    async def fake_virus(client, message):
        if not message.reply_to_message: return
        target = message.reply_to_message.from_user.first_name
        await message.edit("⚠️ **SCANNING MESSAGE...**")
        await asyncio.sleep(1)
        await message.edit(f"☣️ **VIRUS DETECTED in {target}'s text!**")
        await asyncio.sleep(1)
        await message.edit("🗑️ **Quarantining User...**")

    # 2. HACKER ALERT (.alert)
    @userbot.on_message(filters.command("alert", prefixes=".") & filters.me)
    async def hacker_alert(client, message):
        try:
            for i in range(7):
                await message.edit("🔴 **WARNING: SYSTEM BREACH DETECTED!** 🔴\n💀 **HACKER IS HERE** 💀")
                await asyncio.sleep(0.5)
                await message.edit("⚫ **WARNING: SYSTEM BREACH DETECTED!** ⚫\n💀 **HACKER IS HERE** 💀")
                await asyncio.sleep(0.5)
            await message.edit("❌ **SYSTEM DESTROYED** ❌\n(Restart Required)")
        except: pass


# ==========================================
#  ⬇️ NORMAL BOT HANDLERS ⬇️
# ==========================================

@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS:
        await message.reply_text("✅ **Bot Ready!**\nFiles bhejo.")
    else:
        await message.reply_text("🔒 **Locked!** Send Password. password nhi pta to admin se bat kro ( teligram id - @kaal_shadow )")

@bot.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in AUTH_USERS:
        if text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Unlocked! password shi hai files bhejo **")
        else:
            await message.reply_text("❌ Wrong Password. shi password dalo ya admin se bat kro ( teligram id - @kaal_shadow )")
        return

    if "t.me/" in text or "telegram.me/" in text:
        if not userbot: return await message.reply_text("❌ Userbot Missing.")
        try:
            clean_link = text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
            parts = clean_link.split("/")
            if parts[0] == "c": chat_id = int("-100" + parts[1])
            else: chat_id = parts[0]
            msg_id = int(parts[-1].split("?")[0])
            
            target_msg = await userbot.get_messages(chat_id, msg_id)
            m_type = "document"
            if target_msg.photo: m_type = "photo"
            elif target_msg.video: m_type = "video"
            
            media = getattr(target_msg, m_type, None)
            if media:
                if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
                user_queue_numbers[user_id] += 1
                q_pos = user_queue_numbers[user_id]
                queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
                await upload_queue.put( (client, message, media, m_type, target_msg, queue_msg) )
            else:
                await message.reply_text("❌ Media not found.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_file(client, message):
    if message.from_user.id not in AUTH_USERS: return
    user_id = message.from_user.id
    m_type = "document"
    if message.photo: m_type = "photo"
    elif message.video: m_type = "video"
    media = getattr(message, m_type)

    if user_id not in user_queue_numbers: user_queue_numbers[user_id] = 0
    user_queue_numbers[user_id] += 1
    q_pos = user_queue_numbers[user_id]

    queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
    await upload_queue.put( (client, message, media, m_type, None, queue_msg) )

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
