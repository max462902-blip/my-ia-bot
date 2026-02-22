import os
import asyncio
import threading
import logging
from flask import Flask
from pyrogram import Client, filters, idle

# --- SETUP ---
logging.basicConfig(level=logging.INFO) # INFO level taaki sab dikhe
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home(): return "Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", None)
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "kp_2324")

AUTH_USERS = set()

# --- CLIENTS ---
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_handler(client, message):
    logger.info(f"Start command received from {message.from_user.id}")
    await message.reply_text("✅ Bot Online hai bhai!\n🔒 Password bhejo unlock karne ke liye.")

@bot.on_message(filters.text & filters.private)
async def auth_handler(client, message):
    user_id = message.from_user.id
    logger.info(f"Message received: {message.text} from {user_id}")
    
    if user_id not in AUTH_USERS:
        if message.text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 Bot Unlocked! Ab files bhejo.")
        else:
            await message.reply_text("❌ Galat Password.")

async def start_services():
    logger.info("Starting Flask...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    logger.info("Starting Bot...")
    await bot.start()
    
    # Agar session string galat hai to bot yahan nahi phansega
    if SESSION_STRING:
        try:
            logger.info("Starting Userbot...")
            user_bot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
            await user_bot.start()
            logger.info("Userbot Started!")
        except Exception as e:
            logger.error(f"Userbot error (Shayad Session String expired hai): {e}")

    logger.info("✅ SYSTEM FULLY ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_services())            await asyncio.to_thread(api.upload_file, path_or_fileobj=local_path, path_in_repo=final_filename, repo_id=HF_REPO, repo_type="dataset")

            final_link = f"{SITE_URL}/file/{final_filename}"
            if user_id not in user_batches: user_batches[user_id] = []
            user_batches[user_id].append({"name": file_name, "link": final_link, "size": file_size})
            await status_msg.delete()
        except Exception as e:
            if status_msg: await status_msg.edit(f"❌ Error: {e}")
        finally:
            if local_path and os.path.exists(local_path): os.remove(local_path)
            upload_queue.task_done()
        
        if upload_queue.empty():
            await asyncio.sleep(2)
            if user_id in user_batches and user_batches[user_id]:
                res = "✅ **Batch Completed**\n\n"
                for item in user_batches[user_id]:
                    res += f"📂 {item['name']}\n🔗 `{item['link']}`\n📦 {item['size']}\n\n"
                await client.send_message(user_id, res)
                del user_batches[user_id]

# --- HANDLERS ---

@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    # Har kisi ko reply dega jo /start karega
    await message.reply_text(f"👋 Hello {message.from_user.first_name}!\n🔒 Bot Locked hai. Password bhejo.")

@bot.on_message(filters.text & filters.private)
async def handle_txt(client, message):
    user_id = message.from_user.id
    # Agar user unlocked nahi hai
    if user_id not in AUTH_USERS:
        if message.text.strip() == ACCESS_PASSWORD:
            AUTH_USERS.add(user_id)
            await message.reply_text("🔓 **Bot Unlocked!** Ab link ya file bhejo.")
        else:
            await message.reply_text("❌ Galat Password. Sahi dalo.")
        return

    # Agar link hai
    if "t.me/" in message.text:
        if not userbot: 
            return await message.reply_text("❌ Userbot (Session) nahi hai.")
        await message.reply_text("⏳ Processing Link...")
        # Link logic yahan short mein (original logic restored)
        try:
            clean = message.text.split('/')
            chat = int("-100" + clean[-2]) if clean[-3] == 'c' else clean[-2]
            msg_id = int(clean[-1])
            t_msg = await userbot.get_messages(chat, msg_id)
            m_type = "video" if t_msg.video else "photo" if t_msg.photo else "document"
            media = getattr(t_msg, m_type, None)
            if media:
                await upload_queue.put((client, message, media, m_type, t_msg))
        except Exception as e:
            await message.reply_text(f"Link Error: {e}")

@bot.on_message(filters.video | filters.document | filters.photo)
async def handle_files(client, message):
    if message.from_user.id not in AUTH_USERS: 
        return await message.reply_text("🔒 Pehle password dalo.")
    m_type = "video" if message.video else "photo" if message.photo else "document"
    await upload_queue.put((client, message, getattr(message, m_type), m_type, None))

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(worker_processor())
    await bot.start()
    if userbot: await userbot.start()
    print("✅ System Online!")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
