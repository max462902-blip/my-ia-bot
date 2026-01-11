# File ke sabse upar imports mein ye add kar:
import random 

# ... baaki code ...

# Jahan identifier wali line thi, wahan ye likh:
identifier = f"ia_up_{message.chat.id}_{random.randint(1000, 99999)}"

from keep_alive import keep_alive
keep_alive()

import os
import telebot
from internetarchive import upload
from flask import Flask
from threading import Thread

# --- Web Server for Render ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is Alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

# --- Bot Setup ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
IA_ACCESS = os.getenv('IA_ACCESS')
IA_SECRET = os.getenv('IA_SECRET')

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Bhai! Video bhejo, main Archive par daal kar Direct MP4 Link de dunga.")

@bot.message_handler(content_types=['video', 'document'])
def handle_video(message):
    try:
        msg = bot.reply_to(message, "⏳ Archive par upload ho raha hai... Thoda sabar rakho!")
        
        file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        filename = "video.mp4" 
        with open(filename, 'wb') as f:
            f.write(downloaded_file)

        # Archive unique ID
        
        
        # Upload
        upload(identifier, files=[filename], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        # Direct Links (Simple text without Markdown to avoid errors)
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ Upload Success!\n\n"
                   f"🔗 Details Page: {details_link}\n\n"
                   f"🎬 Direct Stream Link: {stream_link}\n\n"
                   f"Note: Stream link 5-10 min baad chalega jab Archive process kar lega.")
        
        # Yahan se parse_mode hata diya hai error fix karne ke liye
        bot.edit_message_text(caption, chat_id=msg.chat.id, message_id=msg.message_id)
        
        os.remove(filename)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    bot.infinity_polling()
