# Lightweight Python base image
FROM python:3.11-slim

# telethon ke liye zaroori build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pehle sirf requirements copy karo (Docker layer caching ke liye fast rebuild)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki code copy karo
COPY bot.py .

# Bot chalao
CMD ["python", "bot.py"]
