import os
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIGURATION (Environment Variables) ---
# Render पर आपको ये Environment Variables में डालने होंगे
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID_HERE"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

app = Client("pdf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Catbox पर अपलोड करने का फंक्शन
def upload_to_catbox(file_path):
    url = "https://catbox.moe/user/api.php"
    data = {
        "reqtype": "fileupload",
        "userhash": ""
    }
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": f}
            response = requests.post(url, data=data, files=files)
            if response.status_code == 200:
                return response.text # यह लिंक रिटर्न करेगा
            else:
                return None
    except Exception as e:
        print(f"Error uploading: {e}")
        return None

@app.on_message(filters.document | filters.video | filters.audio) # PDF और अन्य फाइल्स के लिए
async def handle_document(client, message):
    # चेक करें कि फाइल साइज 400MB से ज्यादा न हो (Render लिमिट के कारण)
    if message.document and message.document.file_size > 400 * 1024 * 1024:
        await message.reply_text("❌ फाइल बहुत बड़ी है। Render Free Tier पर केवल 400MB तक की फाइल भेजें।")
        return

    status_msg = await message.reply_text("📥 **Downloading...**\n\nकृपया प्रतीक्षा करें, यह Render सर्वर पर आ रहा है।")
    
    try:
        # 1. फाइल डाउनलोड करें
        file_path = await message.download()
        
        await status_msg.edit_text("📤 **Uploading to Cloud...**\n\nअब इसे क्लाउड पर भेज रहे हैं ताकि लिंक बन सके।")
        
        # 2. कैटबॉक्स पर अपलोड करें
        link = upload_to_catbox(file_path)
        
        # 3. फाइल डिलीट करें (Render स्टोरेज बचाने के लिए)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if link and "catbox" in link:
            # 4. लिंक और बटन भेजें
            # ` ` (backticks) का इस्तेमाल वन टैप कॉपी के लिए होता है
            
            caption = (
                f"✅ **File Uploaded Successfully!**\n\n"
                f"📂 **File Name:** `{message.document.file_name if message.document else 'File'}`\n\n"
                f"🔗 **One Tap Copy Link:**\n`{link}`"
            )
            
            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📂 Open PDF / File", url=link)]]
            )
            
            await status_msg.edit_text(caption, reply_markup=button)
        else:
            await status_msg.edit_text("❌ अपलोड में कोई त्रुटि हुई। कृपया दोबारा प्रयास करें।")
            
    except Exception as e:
        # अगर कोई एरर आए तो भी लोकल फाइल डिलीट करें
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.edit_text(f"Error: {e}")

print("Bot Started...")
app.run()
