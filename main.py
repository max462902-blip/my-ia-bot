import os
import telebot
from internetarchive import upload
from flask import Flask
from threading import Thread

# --- Render ke liye Chota Web Server (Taaki bot band na ho) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is Running!"

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
        msg = bot.reply_to(message, "⏳ Uploading to Archive... Please Wait!")
        
        # File download setup
        file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        filename = "video.mp4" # Hum filename fix rakhenge taaki link banana asaan ho
        with open(filename, 'wb') as f:
            f.write(downloaded_file)

        # Archive unique ID
        identifier = f"ia_up_{message.chat.id}_{message.message_id}"
        
        # Metadata ke sath upload
        upload(identifier, files=[filename], access_key=IA_ACCESS, secret_key=IA_SECRET, metadata={"mediatype": "movies"})
        
        # Direct Links banana
        details_link = f"https://archive.org/details/{identifier}"
        stream_link = f"https://archive.org/download/{identifier}/{filename}"
        
        caption = (f"✅ **Upload Success!**\n\n"
                   f"🔗 **Details Page:** {details_link}\n"
                   f"🎬 **Direct Stream Link:** `{stream_link}`\n\n"
                   f"Note: Stream link ko chalne mein 5-10 min lag sakte hain jab tak Archive use process na karle.")
        
        bot.edit_message_text(caption, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")
        
        os.remove(filename) # Phone ki memory khali
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Bot aur Server ko sath chalana ---
if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    bot.infinity_polling()
