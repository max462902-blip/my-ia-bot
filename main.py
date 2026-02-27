import os
import threading
import asyncio
import requests
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from dotenv import load_dotenv

load_dotenv()

# --- SERVER (LINK GENERATOR) ---
app = Flask(__name__)
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

@app.route('/')
def home(): return "PDF Bot Online"

@app.route('/view/<file_id>')
def view(file_id):
    try:
        token = os.environ.get("BOT_TOKEN")
        # File Path mangwana Telegram se
        data = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}").json()
        if data['ok']:
            path = data['result']['file_path']
            # Direct Chrome Link
            return redirect(f"https://api.telegram.org/file/bot{token}/{path}")
    except: pass
    return "Error: Link Expired", 404

def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- BOT SETUP ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION = os.getenv("SESSION_STRING")

bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION) if SESSION else None

AUTH = set()
PASS = "kp_2324"

# --- PDF PROCESSOR ---
async def process_pdf(media, msg, original_msg=None):
    try:
        status = await msg.reply("⏳ **Processing PDF...**")
        
        # 1. Filename & Size
        fname = getattr(media, "file_name", "document.pdf")
        if not fname.endswith(".pdf"): fname += ".pdf"
        
        # 2. Download
        path = f"downloads/{fname}"
        if not os.path.exists("downloads"): os.makedirs("downloads")
        
        await status.edit("⬇️ **Downloading...**")
        if original_msg: await original_msg.download(path)
        else: await msg.download(path)
        
        # 3. Upload to Chat
        await status.edit("⬆️ **Uploading...**")
        upl_msg = await msg.reply_document(document=path, caption="⚙️ **Generating Link...**")
        
        # 4. Cleanup & Link
        if os.path.exists(path): os.remove(path)
        
        link = f"{SITE_URL}/view/{upl_msg.document.file_id}"
        
        await upl_msg.edit_caption(
            f"**Chat Box PDF**\n\n"
            f"🏷️ **Name:** `{fname}`\n"
            f"🔗 **One Tap Copy Link:**\n"
            f"`{link}`"
        )
        await status.delete()
        
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# --- HANDLERS ---
@bot.on_message(filters.command("start"))
async def start(_, m):
    if m.from_user.id in AUTH: await m.reply("✅ Send PDF.")
    else: await m.reply("🔒 Password?")

@bot.on_message(filters.text & filters.private)
async def text_handler(_, m):
    if m.from_user.id not in AUTH:
        if m.text == PASS:
            AUTH.add(m.from_user.id)
            await m.reply("🔓 Unlocked! Send PDF.")
        else: await m.reply("❌ Wrong.")
        return

    # Link Logic
    if "t.me/" in m.text and userbot:
        try:
            link = m.text.replace("https://", "").replace("t.me/", "")
            parts = link.split("/")
            chat = int("-100" + parts[1]) if parts[0] == "c" else parts[0]
            msg_id = int(parts[-1].split("?")[0])
            
            t_msg = await userbot.get_messages(chat, msg_id)
            if t_msg.document and t_msg.document.mime_type == "application/pdf":
                await process_pdf(t_msg.document, m, t_msg)
            else:
                await m.reply("❌ Sirf PDF Link bhejo.")
        except Exception as e: await m.reply(f"❌ Error: {e}")

@bot.on_message(filters.document)
async def file_handler(_, m):
    if m.from_user.id in AUTH:
        if m.document.mime_type == "application/pdf":
            await process_pdf(m.document, m)
        else:
            await m.reply("❌ Only PDF allowed.")
    else: await m.reply("🔒 Locked.")

# --- RUN ---
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await bot.start()
    if userbot: await userbot.start()
    await idle()
    await bot.stop()
    if userbot: await userbot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
