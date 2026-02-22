import telebot
import os
from flask import Flask
from threading import Thread

# --- CONFIGURATION ---
# Token hum Render ke Environment Variables se uthayenge (Security ke liye)
API_TOKEN = os.environ.get('BOT_TOKEN')

if not API_TOKEN:
    print("Error: BOT_TOKEN environment variable nahi mila!")
    # Agar local PC pe test krna hai to niche wali line uncomment krke token dal de
    # API_TOKEN = "TERA_BOT_TOKEN_YAHAN"

bot = telebot.TeleBot(API_TOKEN)
server = Flask(__name__)

# --- BOT COMMANDS ---

@bot.message_handler(func=lambda message: message.text and message.text.startswith('.link'))
def send_image_from_link(message):
    try:
        # Command se URL alag karna
        text_parts = message.text.split(maxsplit=1)
        
        if len(text_parts) < 2:
            bot.reply_to(message, "Link toh de bhai! Example: .link https://im.ge/example.jpg")
            return
            
        url = text_parts[1].strip()
        
        # User ko reply
        status_msg = bot.reply_to(message, "Process kar raha hoon...")
        
        # Image bhejna
        bot.send_photo(message.chat.id, url, reply_to_message_id=message.message_id)
        
        # Status message delete (optional)
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except:
            pass

    except Exception as e:
        bot.reply_to(message, f"Error aa gaya: {e}")

# --- RENDER WEB SERVER KEEPALIVE ---

@server.route('/')
def home():
    return "Bot is running fine!"

def run_web():
    # Render PORT environment variable automatically set karta hai
    port = int(os.environ.get("PORT", 5000))
    server.run(host="0.0.0.0", port=port)

def run_bot():
    print("Bot polling start ho gayi...")
    bot.infinity_polling()

if __name__ == "__main__":
    # Web server aur Bot dono ko ek sath chalane ke liye Threading
    t = Thread(target=run_web)
    t.start()
    run_bot()
# --- SIRF YE PART CHANGE KARO ---

def run_bot():
    print("Bot polling start ho gayi...")
    # Ye line add karo:
    bot.remove_webhook() 
    # Thoda delay aur interval add kiya hai taaki crash na ho
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

# --------------------------------
