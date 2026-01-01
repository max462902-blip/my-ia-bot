import os
import telebot
from internetarchive import upload

# Keys Koyeb ke environment variables se aayengi
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
ACCESS = os.getenv('IA_ACCESS')
SECRET = os.getenv('IA_SECRET')

@bot.message_handler(content_types=['video', 'document'])
def handle_video(message):
    msg = bot.reply_to(message, "⏳ Uploading...")
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    filename = "video.mp4"
    with open(filename, 'wb') as f:
        f.write(downloaded_file)
    
    id = f"ia_up_{message.message_id}"
    upload(id, files=[filename], access_key=ACCESS, secret_key=SECRET)
    bot.edit_message_text(f"✅ Link: https://archive.org/details/{id}", msg.chat.id, msg.message_id)
    os.remove(filename)

bot.polling()
