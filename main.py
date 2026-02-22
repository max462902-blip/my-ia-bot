import telebot
import os
import time
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
API_TOKEN = os.environ.get('BOT_TOKEN')

if not API_TOKEN:
    print("Error: BOT_TOKEN nahi mila!")

bot = telebot.TeleBot(API_TOKEN)
server = Flask(__name__)

# --- BOT COMMANDS ---

# 1. Start Command (Ye naya add kiya hai)
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Bhai main online hoon! \nImage bhejne ke liye use karo:\n.link https://example.com/image.jpg")

# 2. Link Handler (Image bhejne wala code)
@bot.message_handler(func=lambda message: message.text and message.text.startswith('.link'))
def send_image_from_link(message):
    try:
        text_parts = message.text.split(maxsplit=1)
        if len(text_parts) < 2:
            bot.reply_to(message, "Link toh de bhai! Example: .link https://im.ge/example.jpg")
            return
            
        url = text_parts[1].strip()
        status_msg = bot.reply_to(message, "Ruk image bhej raha hoon...")
        
        bot.send_photo(message.chat.id, url, reply_to_message_id=message.message_id)
        
        # Safai abhiyaan (Status message delete)
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass

    except Exception as e:
        bot.reply_to(message, f"Link kharab hai ya permission nahi hai.\nError: {e}")

# --- WEB SERVER (Render ke liye) ---

@server.route('/')
def home():
    return "Bot mast chal raha hai!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

def run_bot():
    print("Bot polling start ho gayi...")
    # Purane connection tod kar naya connection (Fixes 429 Error)
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    t = Thread(target=run_web)
    t.start()
    run_bot()
