import os
import asyncio
import threading
import logging
import requests
from flask import Flask, redirect
from pyrogram import Client, filters, idle
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://0.0.0.0:8080")

# --- QUEUE SYSTEM (LOCK) ---
# Ye ensure karega ki ek baar me ek hi file download ho
# Taaki storage full na ho.
QUEUE_LOCK = asyncio.Lock()

# --- WEB SERVER (Link Generator) ---
app = Flask(__name__)

@app.route('/')
def home(): return "Bot is Running..."

@app.route('/view/<file_id>')
def view_file(file_id):
    try:
        # Telegram API se file path lekar redirect karenge
        req = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}")
        resp = req.json()
        if resp['ok']:
            path = resp['result']['file_path']
            return redirect(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}")
    except: pass
    return "❌ Link Expired or Error", 404

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# --- BOT CLIENT ---
bot = Client("pdf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PDF HANDLER ---
@bot.on_message(filters.document)
async def handle_pdf(client, message):
    # Sirf PDF Check
    if not message.document.mime_type == "application/pdf":
        return await message.reply("❌ Sirf PDF bhejo.")

    status = await message.reply("⏳ **Added to Queue...** (Waiting for turn)")
    
    # --- QUEUE START ---
    # Jab tak pehli file delete nahi hoti, dusri wait karegi
    async with QUEUE_LOCK:
        local_path = None
        try:
            await status.edit("⬇️ **Downloading...**")
            
            # 1. Download
            local_path = await message.download()
            
            # 2. Upload to Chat Box
            await status.edit("⬆️ **Uploading to Chat...**")
            uploaded_msg = await message.reply_document(
                document=local_path,
                caption="⚙️ **Generating Link...**"
            )

            # 3. Generate Link
            file_id = uploaded_msg.document.file_id
            view_link = f"{SITE_URL}/view/{file_id}"

            # 4. Edit Caption
            original_name = message.document.file_name
            await uploaded_msg.edit_caption(
                f"**Chat Box PDF**\n\n"
                f"🏷️ **Name:** `{original_name}`\n"
                f"🔗 **One Tap Copy Link:**\n"
                f"`{view_link}`"
            )
            await status.delete()

        except Exception as e:
            await status.edit(f"❌ Error: {e}")
        
        finally:
            # 5. STORAGE CLEANUP (Sabse Important)
            # Chahe error aaye ya success, file delete honi chahiye
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
                print(f"Deleted: {local_path}")

# --- START ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run()
