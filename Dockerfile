FROM python:3.10-slim

# वर्किंग डायरेक्टरी सेट करें
WORKDIR /app

# ज़रूरी फाइलें कॉपी करें
COPY . .

# लाइब्रेरीज़ इनस्टॉल करें
RUN pip install --no-cache-dir -r requirements.txt

# बॉट को स्टार्ट करने की कमांड
CMD ["python", "main.py"]
