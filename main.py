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
    # ?download=true hata diya taki Chrome view kare
    real_url = f"https://huggingface.co/datasets/{hf_repo}/resolve/main/{filename}"
    return redirect(real_url, code=302)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_REPO = os.getenv("HF_REPO")
SESSION_STRING = os.getenv("SESSION_STRING")

# --- SECURITY ---
ACCESS_PASSWORD = "kp_2324"
AUTH_USERS = set()

# --- GLOBAL VARIABLES ---
PRANK_ACTIVE = True  # Master Switch (Default ON)

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

            # Direct HF Link (For Chrome View)
            final_link = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{final_filename}"
            
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
#  ⬇️ 🔥 NEW FEATURES & PRANKS 🔥 ⬇️
# ==========================================

if userbot:

    # 🟢 1. MASTER SWITCH (.prankon / .prankoff)
    @userbot.on_message(filters.command("prankon", prefixes=".") & filters.me)
    async def enable_prank(client, message):
        global PRANK_ACTIVE
        PRANK_ACTIVE = True
        await message.edit("🟢 **MASTER SWITCH:** PRANK MODE **ON**")

    @userbot.on_message(filters.command("prankoff", prefixes=".") & filters.me)
    async def disable_prank(client, message):
        global PRANK_ACTIVE
        PRANK_ACTIVE = False
        await message.edit("🔴 **MASTER SWITCH:** PRANK MODE **OFF**")


    # 🖼️ 2. HACKER BACKGROUND TEXT (.text <msg>)
    @userbot.on_message(filters.command("text", prefixes=".") & filters.me)
    async def hacker_bg_text(client, message):
        if not PRANK_ACTIVE: return # Agar switch OFF hai to kaam nahi karega
        try:
            if len(message.command) < 2: return
            text_content = message.text.split(maxsplit=1)[1]
            
            # Hacker Image URL (Matrix/Anonymous)
            hacker_img = "https://w0.peakpx.com/wallpaper/168/223/HD-wallpaper-hacker-binary-code-matrix-technology.jpg"
            
            await message.delete()
            await client.send_photo(
                chat_id=message.chat.id,
                photo=hacker_img,
                caption=f"💻 **SECURE TRANSMISSION** 💻\n\n`{text_content}`\n\n💀 **ENCRYPTED MSG**"
            )
        except: pass


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
    #  EXISTING PRANKS (WITH MASTER SWITCH CHECK)
    # ----------------------------------------------------

    # .tokon
    @userbot.on_message(filters.command("tokon", prefixes=".") & filters.me)
    async def break_text(client, message):
        if not PRANK_ACTIVE: return # Check added
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

    # .hack
    @userbot.on_message(filters.command("hack", prefixes=".") & filters.me)
    async def complex_hack(client, message):
        if not PRANK_ACTIVE: return
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

    # .glitch (5 Mins)
    @userbot.on_message(filters.command("glitch", prefixes=".") & filters.me)
    async def glitch_mode(client, message):
        if not PRANK_ACTIVE: return
        try:
            if message.reply_to_message and message.reply_to_message.text:
                target_text = message.reply_to_message.text
            elif len(message.command) > 1:
                target_text = message.text.split(maxsplit=1)[1]
            else: target_text = "SYSTEM FAILURE"

            end_time = time.time() + 300 
            while time.time() < end_time:
                try:
                    await message.edit(f"**{target_text}**")
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    await message.edit("⠀") 
                    await asyncio.sleep(random.uniform(0.2, 1.0))
                    glitch_chars = "¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿"
                    half = len(target_text) // 2
                    corrupted = target_text[:half] + "".join(random.choice(glitch_chars) for _ in range(6))
                    await message.edit(f"`{corrupted}`")
                    await asyncio.sleep(random.uniform(0.3, 1.5))
                except Exception as e: break
            await message.edit("❌ **CONNECTION LOST** ❌")
        except: pass

    # .scan (Detailed)
    @userbot.on_message(filters.command("scan", prefixes=".") & filters.me)
    async def scan_user(client, message):
        if not PRANK_ACTIVE: return
        if not message.reply_to_message:
            await message.edit("❌ **Reply to a user!**")
            return
        try:
            user = message.reply_to_message.from_user
            target_msg = message.reply_to_message.text or "[Media]"
            await message.edit("🔍 **INITIALIZING SCAN...**")
            await asyncio.sleep(1)
            await message.edit("📡 **FETCHING DATABASE RECORDS...**")
            await asyncio.sleep(1)
            await message.edit("🔐 **BYPASSING SECURITY PROTOCOLS...**")
            await asyncio.sleep(1)
            
            # Data Generation
            name = user.first_name
            full_name = f"{name} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "No Username"
            fake_phone = f"+91 {random.randint(600, 999)}xxxxx{random.randint(10, 99)}"
            total_msgs = random.randint(35, 5000)
            topics = ["Love", "Paisa", "Settings", "Daru", "Admin", "Hacking", "Dhoka", "Notes"]
            fav_topic = random.choice(topics)
            online_count = random.randint(5, 150)
            left_count = random.randint(0, 10)
            now = datetime.now()
            day = now.strftime("%A")
            time_str = now.strftime("%H:%M:%S")

            report = f"""
☠️ **USER REPORT DETECTED** ☠️

👤 **IDENTITY:**
• Name: {full_name}
• ID: `{user.id}`
• User: {username}
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
            await message.edit(report)
        except: pass

    # .type
    @userbot.on_message(filters.command("type", prefixes=".") & filters.me)
    async def type_text(client, message):
        if not PRANK_ACTIVE: return
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

    # .kaal
    @userbot.on_message(filters.command("kaal", prefixes=".") & filters.me)
    async def kaal_mode(client, message):
        if not PRANK_ACTIVE: return
        try:
            if len(message.command) < 2: text = "KAAL SHADOW"
            else: text = message.text.split(maxsplit=1)[1]
            await message.edit("☠️ **KAAL** ☠️")
            await asyncio.sleep(1)
            styles = [f"**{text}**", f"___{text}___", f"`{text}`", f"||{text}||", f"~~{text}~~", f"[{text}]", f"🔥 {text} 🔥"]
            for style in styles:
                await message.edit(style)
                await asyncio.sleep(0.8)
            await message.edit(f"👑 **{text}** 👑")
        except: pass

    # .virus
    @userbot.on_message(filters.command("virus", prefixes=".") & filters.me)
    async def fake_virus(client, message):
        if not PRANK_ACTIVE: return
        if not message.reply_to_message: return
        await message.edit("⚠️ **SCANNING MESSAGE...**")
        await asyncio.sleep(1)
        await message.edit(f"☣️ **VIRUS DETECTED!**")
        await asyncio.sleep(1)
        await message.edit("🗑️ **Quarantining User...**")

    # .alert
    @userbot.on_message(filters.command("alert", prefixes=".") & filters.me)
    async def hacker_alert(client, message):
        if not PRANK_ACTIVE: return
        try:
            for i in range(7):
                await message.edit("🔴 **WARNING: SYSTEM BREACH DETECTED!** 🔴\n💀 **HACKER IS HERE** 💀")
                await asyncio.sleep(0.5)
                await message.edit("⚫ **WARNING: SYSTEM BREACH DETECTED!** ⚫\n💀 **HACKER IS HERE** 💀")
                await asyncio.sleep(0.5)
            await message.edit("❌ **SYSTEM DESTROYED** ❌\n(Restart Required)")
        except: pass

    # .run (Self Destruct)
    @userbot.on_message(filters.command("run", prefixes=".") & filters.me)
    async def self_destruct(client, message):
        if not PRANK_ACTIVE: return
        await message.edit("💣 **Deleting in 5s...**")
        for i in range(5, 0, -1):
            await message.edit(f"💣 **{i}**")
            await asyncio.sleep(1)
        await message.edit("💥")
        await asyncio.sleep(0.5)
        await message.delete()

    # Auto Jitu Defender (Respect)
    @userbot.on_message(filters.group & ~filters.me)
    async def jitu_def(client, message):
        if not PRANK_ACTIVE: return # Ye bhi off ho jayega agar master switch off hai
        if message.text and "jitu" in message.text.lower():
            try: await message.reply_text("🗣️ **Oye!** Jitu nahi, **Kaal Shadow** bol! 🤫")
            except: pass

# ==========================================
#  ⬇️ NORMAL BOT START ⬇️
# ==========================================
@bot.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in AUTH_USERS: await message.reply_text("✅ Bot Online!")
    else: await message.reply_text("🔒 Locked!")

@bot.on_message(filters.text & filters.private)
async def auth_and_link(client, message):
    if message.text == ACCESS_PASSWORD:
        AUTH_USERS.add(message.from_user.id)
        await message.reply_text("🔓 Unlocked!")
    elif message.from_user.id in AUTH_USERS and "t.me/" in message.text:
        # Link Handler Logic
        if not userbot: return await message.reply_text("❌ Userbot Missing.")
        try:
            clean_link = message.text.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "")
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
                if message.from_user.id not in user_queue_numbers: user_queue_numbers[message.from_user.id] = 0
                user_queue_numbers[message.from_user.id] += 1
                q_pos = user_queue_numbers[message.from_user.id]
                queue_msg = await message.reply_text(f"🕒 **Added to Queue** (No. {q_pos})", quote=True)
                await upload_queue.put( (client, message, media, m_type, target_msg, queue_msg) )
            else:
                await message.reply_text("❌ Media not found.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_media(client, message):
    if message.from_user.id in AUTH_USERS:
        m_type = "video" if message.video else "photo" if message.photo else "document"
        q_pos = upload_queue.qsize() + 1
        q_msg = await message.reply_text(f"🕒 Queue No. {q_pos}")
        await upload_queue.put((client, message, getattr(message, m_type), m_type, None, q_msg))

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
