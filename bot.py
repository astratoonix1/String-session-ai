"""
Personal Telegram Auto-Reply Userbot (Render-ready)
- Aapke apne account (string session) se chalta hai
- Sirf private DM par reply karta hai (group/channel/bots skip)
- Optional: Gemini AI (gemini-3.6-flash) se dynamic smart reply,
  warna fixed AUTO_REPLY_MESSAGE bhejega
- Sab config Environment Variables se aata hai (Render dashboard me set karna)
"""

import os
import time
import logging
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("autoreply-bot")

# ==== ENVIRONMENT VARIABLES (Render dashboard -> Environment me set karo) ====
API_ID = int(os.environ["API_ID"])                     # required, my.telegram.org se
API_HASH = os.environ["API_HASH"]                       # required
STRING_SESSION = os.environ["STRING_SESSION"]            # required

AUTO_REPLY_MESSAGE = os.environ.get(
    "AUTO_REPLY_MESSAGE",
    "Hi! Main abhi available nahi hoon, jaldi reply karunga. 🙏"
)
COOLDOWN = int(os.environ.get("COOLDOWN_SECONDS", 1800))   # default 30 min

USE_GEMINI = os.environ.get("USE_GEMINI", "false").lower() == "true"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_SYSTEM_PROMPT = os.environ.get(
    "GEMINI_SYSTEM_PROMPT",
    "Tum ek polite auto-reply assistant ho jo kisi vyakti ke Telegram DM ka "
    "short, friendly reply Hinglish me deta hai, batate hue ki wo abhi busy hai "
    "aur jaldi reply karega. Reply 2 lines se zyada lamba mat rakho."
)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
last_replied = {}  # user_id -> last reply timestamp


def get_gemini_reply(incoming_text: str) -> str:
    """Gemini API se dynamic reply generate karo. Fail hone par static message return karo."""
    try:
        payload = {
            "system_instruction": {"parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": incoming_text}]}],
        }
        resp = requests.post(GEMINI_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini call fail hua, static message use kar rahe hain: {e}")
        return AUTO_REPLY_MESSAGE


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    # Sirf private DM — group/channel skip
    if not event.is_private:
        return

    # Khud ka bheja message skip (event.out hi kaafi hai, is_self attribute exist nahi karta)
    if event.out:
        return

    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    user_id = sender.id
    now = time.time()

    # Cooldown — spam se bachne ke liye
    if user_id in last_replied and (now - last_replied[user_id]) < COOLDOWN:
        return

    if USE_GEMINI and GEMINI_API_KEY:
        reply_text = get_gemini_reply(event.raw_text or "")
    else:
        reply_text = AUTO_REPLY_MESSAGE

    await event.reply(reply_text)
    last_replied[user_id] = now
    log.info(f"Auto-reply sent -> {getattr(sender, 'first_name', 'Unknown')} ({user_id})")


class _HealthCheckHandler(BaseHTTPRequestHandler):
    """Render (Web Service type) ko khush karne ke liye dummy HTTP server.
    Agar service ko Background Worker banate ho, iski zaroorat nahi padegi."""

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # Render access logs ko spam hone se rokne ke liye


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthCheckHandler)
    log.info(f"Dummy health-check server chalu hua port {port} par")
    server.serve_forever()


def main():
    # Dummy HTTP server ek alag thread me — sirf Render Web Service ke port-check ke liye
    threading.Thread(target=start_health_server, daemon=True).start()

    log.info("Bot start ho raha hai...")
    client.start()
    log.info("Bot chalu ho gaya, messages sunn raha hai.")
    client.run_until_disconnected()


if __name__ == "__main__":
    main()
  
