import os
import random
import asyncio
import threading
from flask import Flask
from pyrogram import Client, filters, idle, enums
from dotenv import load_dotenv

# --- 1. SETUP (Purana system hi hai) ---
load_dotenv()

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

if not SESSION_STRING:
    print("❌ Error: SESSION_STRING missing! .env file check kar.")
    exit()

# --- 2. SERVER (24/7 Run ke liye) ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Jitu ka Super Roast Bot Running! 🔥"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# --- 3. BOT CLIENT ---
app = Client("jitu_roast_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# --- 4. CONFIGURATION ---
TARGET_USER = "hyr000"   # Shikaar ka Username
IS_RUNNING = False       # Control Switch

# --- 5. MASSIVE SHAYARI DATABASE (50+ Lines) ---
roast_database = [
    # --- Category: Dimaag (Brain) ---
    "🧠 Dimaag hai ya khaali matka?\nTera message padh ke main wahin atka! 😂",
    "💡 Jitna dimaag hai utna hi use kar,\nZyada zor dalega to fuse ud jayega dhyan dhar!",
    "🧐 Einstein ne kaha tha relativity ka rule,\nPar tujhe dekh ke lagta hai tu hai april fool!",
    "🔋 Battery low hai, charger laga le,\nMessage karne se pehle thoda dimaag laga le!",
    "🚮 Kachre ke dabba, naali ka keeda,\nTujhse baat karna hai sabse bada peeda!",
    "🛑 Signal tod ke bhaagi car,\nTere dimaag mein hai gobar, mere yaar!",
    "🦴 Kutta bhonke, haathi chale,\nTera dimaag shayad ghutne mein pale!",
    
    # --- Category: Shakal (Face) ---
    "🥔 Aloo lelo, Kanda lelo,\nIs bande ko group se nikaal ke danda dedo!",
    "👺 Chand se pucho sitaron ka haal,\nApni shakal dekh, jaise ubla hua laal rumaal!",
    "🌚 Poonam ka chaand, amaavas ki raat,\nShakal dekh ke lagta hai hui hai barsaat!",
    "💄 Makeup laga ke bhi tu lagta hai bhoot,\nJaldi bhaag yahan se, warna padegi joot!",
    "🥥 Nariyal ka pani, nimbu ka ras,\nTeri shakal dekh ke ulti aa gayi bas!",
    "🧟‍♂️ Zombie ki chaal, Dracula ka daant,\nTu hai is group ka sabse bada... shant!",
    
    # --- Category: Bolna (Talk) ---
    "🌹 Phoolon ki khushbu, kaliyon ka haar,\nChup kar ja bhai, tera muh hai bekaar!",
    "🤐 Chain ki saans lene de humein,\nTere messages se pollution fail raha hai kasam se!",
    "🌊 Samundar ke kinare, lehron ka shor,\nBas kar bhai, tu hai pakka bore!",
    "🔇 Mute ka button dabana padega,\nTera muh band karaana padega!",
    "🗣️ Jitna tu bolta hai, utna agar sochta,\nTo aaj tu gutter mein nahi, mahal mein hota!",
    "🚂 Train ki patri, engine ka dhuan,\nTu chup rahe to lagega sab naya!",
    
    # --- Category: Insult (General) ---
    "☁️ Aasman mein baadal, zameen pe ghaas,\nTu group mein aata hai to lagta hai bakwaas!",
    "🚽 Toilet ka flush, gutter ka paani,\nMat suna humein apni ye boring kahani!",
    "🍎 An apple a day keeps the doctor away,\nBut your face keeps everyone away!",
    "💻 Computer mein virus, Mobile mein bug,\nTu hai is group ka sabse bada... Mug!",
    "🧱 Deewar pe deewar, uspe cement,\nTere message ka zero percent hai content!",
    "🦍 Roses are red, sky is blue,\nMonkey is in zoo, what are you doing here bro?",
    "🏃‍♂️ Bhaag Milkha Bhaag,\nTera message dekh ke lag gayi aag!",
    "🎪 Circus ka joker, mele ka bhaalu,\nTu dikhta hai jaise sada hua aalu!",
    "🐜 Cheeti chadhi pahaad pe, marne ke waaste,\nTu message karta hai humein pakaane ke waaste!",
    "💊 Dawai ki goli, injection ki sui,\nTu hai wahi jisko dekh ke ladki bhaag gayi!",
    "🧹 Jhaadu laga ke kachra saaf karo,\nIs bande ko group se maaf karo!",
    "🚑 Ambulance bulao, koi behosh hua hai,\nIska joke sunke dimaag khamosh hua hai!",
    "🐸 Mendhak ki tarah tar-tar mat kar,\nInsaan hai to insaano wali baat kar!",
    "🛸 Aliens aaye the tujhe lene,\nPar teri shakal dekh ke wapis bhaag gaye!",
    "🚮 Recycle bin bhi tujhe accept na kare,\nItna trash messages koi kaise bhare!",
    "🍳 Anda ubla, gas gayi jal,\nTu yahan se nikal, aaj nahi to kal!",
    "🧂 Namak swaadanusaar, Joota aukaat-anusaar,\nTujhe milna chahiye dusre wala yaar!",
    "🧼 Sabun se muh dho, sanitizer se haath,\nFir bhi ganda hi rahega tera har ek baat!",
    "🌵 Registan mein cactus, bagiche mein phool,\nTujhse baat karna hai meri sabse badi bhool!",
    "🚦 Traffic light laal hai, ruk ja mere bhai,\nTeri baaton mein hai sirf aur sirf burayi!",
    "📱 Phone tera mehenga, baatein teri sasti,\nKahan se seekhi tune ye cheap masti?",
    "🦗 Jhingur sa shor, macchar sa dhang,\nTere aate hi ho jata hai mahaul tang!",
    "🌧️ Baarish ka paani, sadak ka kichad,\nTu hai is group ka sabse bada fisfaddi teetar!",
    "🎈 Gubbara phoota, hawa nikal gayi,\nTera message padh ke meri hansi nikal gayi (mazaak mein)!",
    "🛌 So ja bhai, dimaag ko rest de,\nHumein aur kitna torture karega, give it a rest de!",
    "🧱 Eent ka jawaab patthar se denge,\nTere har message ka badla hum lenge!",
    "🤥 Jhooth bolna paap hai,\nAur tera yahan hona humare liye shraap hai!",
    "🗑️ Dustbin dhoondh raha hu,\nTere messages wahan daalne ke liye!",
    "🐔 Murga bole kukdookoo,\nBas kar bhai, kitna pakaayega tu!",
    "🕸️ Makdi ka jaala, dhoop ka chashma,\nTera dimaag hai poora ka poora chashma (khokhla)!",
    "🕶️ Kala chashma jachda hai tere mukhde pe,\nKyunki usse teri shakal chup jaati hai dukhde se!"
]

# --- 6. COMMANDS (.start / .stop) ---

@app.on_message(filters.command("start", prefixes=".") & filters.me)
async def start_bot(client, message):
    global IS_RUNNING
    IS_RUNNING = True
    await message.edit(f"✅ **Jitu AI Activated!**\nTarget: @{TARGET_USER} 🎯\nList Size: {len(roast_database)} Shayaris Loaded! 🔥")

@app.on_message(filters.command("stop", prefixes=".") & filters.me)
async def stop_bot(client, message):
    global IS_RUNNING
    IS_RUNNING = False
    await message.edit("🛑 **Jitu AI Stopped!**\nShanti... finally! 😴")

# --- 7. AUTO REPLY LOGIC ---

@app.on_message(filters.group & ~filters.me)
async def handle_roast(client, message):
    global IS_RUNNING
    
    if not IS_RUNNING:
        return

    if message.from_user and message.from_user.username:
        if message.from_user.username.lower() == TARGET_USER.lower():
            try:
                # 3-5 Second ka delay taaki fake na lage
                await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
                await asyncio.sleep(random.randint(3, 5)) 
                
                # Random Shayari pick karna
                roast = random.choice(roast_database)
                
                final_text = (
                    f"🤖 **SYSTEM ALERT** 🤖\n\n"
                    f"🗣️ *Bhai main Gemini 3 hu... Jitu ne jabarn pakad ke mujhe is bhai ke group main le aaya. Main majboor hu!* 😭\n\n"
                    f"🎙️ **Tere liye khaas bezzati:**\n"
                    f"✨ __{roast}__ ✨"
                )
                
                await message.reply_text(final_text, quote=True)
                
            except Exception as e:
                print(f"Error: {e}")

# --- 8. RUNNER ---
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print(f"🚀 Bot Started with {len(roast_database)} Shayaris!")
    app.start()
    idle()
    app.stop()
