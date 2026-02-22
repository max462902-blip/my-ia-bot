# Python ka chhota version use karenge
FROM python:3.9-slim

# Working directory set karenge
WORKDIR /app

# Files copy karenge
COPY . /app

# Libraries install karenge
RUN pip install --no-cache-dir -r requirements.txt

# Bot start karenge
CMD ["python", "main.py"]
