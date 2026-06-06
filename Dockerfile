FROM python:3.10-slim

# FFmpeg इन्स्टॉल करने के लिए (यह YouTube वीडियो के लिए बहुत ज़रूरी है)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# सारे फाइल्स को सर्वर में कॉपी करें
COPY . .

# requirements.txt से सारी लाइब्रेरी इन्स्टॉल करें
RUN pip install --no-cache-dir -r requirements.txt

# बॉट चालू करने की कमांड
CMD ["python", "bot.py"]
