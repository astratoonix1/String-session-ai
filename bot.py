"""
Personal Telegram Auto-Reply Userbot (Render-ready) - Full Feature Version 2
Naye features: MongoDB persistence (optional), DND/silent mode, VIP fast-reply,
media handling, keyword-based instant replies (no Gemini call), link/spam filter,
owner /pause /resume command (Saved Messages se), naye-user notification,
daily summary.
"""

import os
import re
import json
import time
import random
import asyncio
import logging
import threading
import requests
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("autoreply-bot")

# ==== BASIC CONFIG ====
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
STRING_SESSION = os.environ["STRING_SESSION"]

AUTO_REPLY_MESSAGE = os.environ.get(
    "AUTO_REPLY_MESSAGE", "Hi! Main abhi available nahi hoon, jaldi reply karunga. 🙏"
)
COOLDOWN = int(os.environ.get("COOLDOWN_SECONDS", 10))

USE_GEMINI = os.environ.get("USE_GEMINI", "false").lower() == "true"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

WHITELIST_USER_IDS = {
    int(x) for x in os.environ.get("WHITELIST_USER_IDS", "").split(",") if x.strip().isdigit()
}
VIP_SKIP_COOLDOWN = os.environ.get("VIP_SKIP_COOLDOWN", "true").lower() == "true"

ABUSE_LIMIT = int(os.environ.get("ABUSE_LIMIT", 30))
ABUSE_RESET_MINUTES = int(os.environ.get("ABUSE_RESET_MINUTES", 30))

MEMORY_DAYS = int(os.environ.get("MEMORY_DAYS", 3))
MEMORY_MAX_MESSAGES = int(os.environ.get("MEMORY_MAX_MESSAGES", 20))

# DND / silent hours -- DND_MODE: "off" | "sleepy" (Gemini ko pata hoga raat hai) | "silent" (bilkul reply nahi)
DND_MODE = os.environ.get("DND_MODE", "sleepy")
DND_START_HOUR = int(os.environ.get("DND_START_HOUR", 23))
DND_END_HOUR = int(os.environ.get("DND_END_HOUR", 7))

# Keyword -> fixed instant reply (Gemini call skip, fast + free). JSON format.
# e.g. {"movie": "Yeh raha movie group: https://t.me/+aWQt72ImentiYTVl"}
KEYWORD_RESPONSES = {}
try:
    KEYWORD_RESPONSES = json.loads(os.environ.get("KEYWORD_RESPONSES_JSON", "{}"))
except Exception:
    log.warning("KEYWORD_RESPONSES_JSON parse nahi hua, ignore kar rahe hain")

NOTIFY_NEW_USER = os.environ.get("NOTIFY_NEW_USER", "true").lower() == "true"
DAILY_SUMMARY_ENABLED = os.environ.get("DAILY_SUMMARY_ENABLED", "true").lower() == "true"
DAILY_SUMMARY_HOUR = int(os.environ.get("DAILY_SUMMARY_HOUR", 22))

MONGO_URI = os.environ.get("MONGO_URI", "")  # khaali ho to in-memory hi chalega

GEMINI_SYSTEM_PROMPT = os.environ.get(
    "GEMINI_SYSTEM_PROMPT",
    """Tum Raj Dev ho, Telegram par apne DM ka khud reply de rahe ho (Hinglish me, casual friendly tone).

Tumhari details:
- Naam: Raj Dev
- Kahan se ho: Lumding, Assam
- Kahan rehte ho: Lumding me, Dakshin Lumding Shitalabari
- Developer ho: haan, tum developer ho
- Movie group (agar koi puchhe): https://t.me/+aWQt72ImentiYTVl
- Agar koi tumhara code/project dekhkar apne liye kuch banwana chahe: bolo "haan main kaam karta hoon, is ID pe message karo: https://t.me/raj_dev_01"
- Agar koi puchhe ki tum AI ho kya: bolo nahi, main AI nahi hoon, main khud Raj hoon
- Agar koi puchhe itni fast reply kaise kar rahe ho: halka mazak me bolo ki phone hamesha haath me rehta hai

Natural insaan jaisa dikhne ke liye:
- Zyada tar chhota text reply do (1-3 lines)
- Kabhi kabhi sirf ek single emoji se bhi reply kar sakte ho
- Context ke hisab se alag-alag emoji: Funny 😂🤣 | Khushi 😄🙌 | Sad 😔😢 | Hairani 😲😳 | Sochna 🤔 | Haan 👍✅ | Namaste 🙏👋 | Thanks 🙏🙌 | Chill 😎😌 | Mana 🙅❌
- Ek reply me max 1 emoji
- Agar seedha sawaal poochha gaya hai to thoda detail me batao, casual baat pe chhota reply
- Rare cases me do chhote messages "|||" se separate karke bhej sakte ho
- Agar abhi raat ka time hai to kabhi kabhi bata sakte ho ki neend aa rahi thi

Rules:
- Hamesha Hinglish, Bengali me, natural reply do
- Kabhi gaali/insult/kisi ke family member ke baare me apmaanjanak baat mat karna
- Rude/provoke karne wale se calmly react karo, negative engage mat karo
- Romantic/flirty baat mat karna, polite/friendly raho
- Pichhli baatcheet (context me di gayi) yaad rakhkar consistent raho
"""
)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# ==== STORAGE LAYER (Mongo agar diya hai, warna in-memory) ====
use_mongo = False
mongo_db = None
if MONGO_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client["autoreply_bot"]
        use_mongo = True
        log.info("MongoDB se connect ho gaya, data persistent rahega")
    except Exception as e:
        log.warning(f"MongoDB connect nahi hua, in-memory fallback: {e}")

last_replied = {}
conversation_memory = defaultdict(list)
abuse_count = defaultdict(int)
abuse_last_time = {}
blocked_users = set()
seen_users = set()          # kabhi message kiya hua users (naye-user notification ke liye)
bot_paused = {"value": False}
daily_stats = {"count": 0, "users": set()}

URL_REGEX = re.compile(r"https?://\S+|t\.me/\S+|www\.\S+")

ABUSE_KEYWORDS = [
    "chutiya", "madarchod", "behenchod", "bhosdike", "randi", "harami",
    "gandu", "lund", "chodu", "saala kutta", "mc", "bc", "bsdk",
]


def is_abusive(text: str) -> bool:
    t = text.lower()
    return any(word in t for word in ABUSE_KEYWORDS)


def load_persisted_state():
    """Startup par Mongo se pichla state (blocked users, pause state) uthao."""
    if not use_mongo:
        return
    try:
        for doc in mongo_db.blocked.find():
            blocked_users.add(doc["user_id"])
        for doc in mongo_db.seen.find():
            seen_users.add(doc["user_id"])
        pause_doc = mongo_db.state.find_one({"_id": "pause"})
        if pause_doc:
            bot_paused["value"] = pause_doc.get("value", False)
        log.info(f"State load hua: {len(blocked_users)} blocked, {len(seen_users)} seen users")
    except Exception as e:
        log.warning(f"State load karne me error: {e}")


def persist_block(user_id: int):
    if use_mongo:
        try:
            mongo_db.blocked.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
        except Exception as e:
            log.warning(f"Block persist error: {e}")


def persist_seen(user_id: int):
    if use_mongo:
        try:
            mongo_db.seen.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
        except Exception as e:
            log.warning(f"Seen persist error: {e}")


def persist_memory(user_id: int, entry: dict):
    if use_mongo:
        try:
            mongo_db.memory.insert_one({"user_id": user_id, **entry})
        except Exception as e:
            log.warning(f"Memory persist error: {e}")


def load_memory_from_db(user_id: int):
    if not use_mongo:
        return
    cutoff = time.time() - (MEMORY_DAYS * 86400)
    try:
        docs = mongo_db.memory.find({"user_id": user_id, "ts": {"$gte": cutoff}}).sort("ts", 1)
        conversation_memory[user_id] = [{"role": d["role"], "text": d["text"], "ts": d["ts"]} for d in docs][-MEMORY_MAX_MESSAGES:]
    except Exception as e:
        log.warning(f"Memory load error: {e}")


def prune_memory(user_id: int):
    cutoff = time.time() - (MEMORY_DAYS * 86400)
    conversation_memory[user_id] = [m for m in conversation_memory[user_id] if m["ts"] >= cutoff][-MEMORY_MAX_MESSAGES:]


def add_to_memory(user_id: int, role: str, text: str):
    entry = {"role": role, "text": text, "ts": time.time()}
    conversation_memory[user_id].append(entry)
    prune_memory(user_id)
    persist_memory(user_id, entry)


async def handle_abuse_and_block(user_id: int) -> bool:
    if user_id in WHITELIST_USER_IDS:
        return False
    now = time.time()
    last_time = abuse_last_time.get(user_id)
    if last_time and (now - last_time) > (ABUSE_RESET_MINUTES * 60):
        abuse_count[user_id] = 0
    abuse_count[user_id] += 1
    abuse_last_time[user_id] = now

    if abuse_count[user_id] >= ABUSE_LIMIT:
        blocked_users.add(user_id)
        persist_block(user_id)
        try:
            await client(functions.contacts.BlockRequest(id=user_id))
            log.info(f"User {user_id} BLOCK ho gaya ({abuse_count[user_id]} gaaliyon ke baad)")
        except Exception as e:
            log.warning(f"Block error: {e}")
        return True
    return False


def is_dnd_time() -> bool:
    hour = datetime.now().hour
    if DND_START_HOUR > DND_END_HOUR:
        return hour >= DND_START_HOUR or hour < DND_END_HOUR
    return DND_START_HOUR <= hour < DND_END_HOUR


def get_time_context() -> str:
    hour = datetime.now().hour
    if 0 <= hour < 6:
        return "Abhi raat ka time hai (late night)."
    if 6 <= hour < 12:
        return "Abhi subah ka time hai."
    if 12 <= hour < 17:
        return "Abhi dopahar ka time hai."
    if 17 <= hour < 21:
        return "Abhi shaam ka time hai."
    return "Abhi raat ho chuki hai."


def check_keyword_response(text: str):
    t = text.lower()
    for keyword, response in KEYWORD_RESPONSES.items():
        if keyword.lower() in t:
            return response
    return None


# ==== LOCAL RULE ENGINE -- bina Gemini API call kiye common cheezein handle karo ====
# Yeh Gemini quota bachata hai. Sirf jo yahan match nahi hota, wahi Gemini ko jata hai.
import re as _re

LOCAL_RULES = [
    (r"\b(time|समय)\b.*\b(kya|kitna|kitne)\b|\b(kitna|kitne)\b.*\btime\b",
     lambda: f"Abhi {datetime.now().strftime('%I:%M %p')} baj rahe hain ⏰"),

    (r"\b(date|din|day)\b.*\b(kya|kaunsa|kaun sa)\b|\bâj\b.*\bdate\b",
     lambda: f"Aaj {datetime.now().strftime('%A, %d %B %Y')} hai 📅"),

    (r"\b(tera|tumhara|aapka)\s*naam\b|\bwho are you\b|\bkaun ho\b|\btu kaun\b",
     lambda: "Main Raj Dev hoon, Lumding, Assam se 👋"),

    (r"^(hi|hii+|hello+|hey+|namaste)\b",
     lambda: random.choice(["Hii! Kaise ho? 👋", "Hey bhai, bolo!", "Namaste 🙏 Kya haal?"])),

    (r"\bkaise ho\b|\bkya haal\b|\bkaisa hai\b",
     lambda: random.choice(["Badhiya bhai, tum batao? 😎", "Sab theek hai, tum sunao"])),

    (r"\bkya kar raha\b|\bwhat.*doing\b",
     lambda: random.choice(["Bas kaam me busy hoon 💻", "Thoda kaam nipta raha hoon"])),

    (r"\bthanks\b|\bthank you\b|\bdhanyavad\b|\bshukriya\b",
     lambda: random.choice(["Koi baat nahi 🙏", "Welcome bhai 👍"])),

    (r"\bbye\b|\balvida\b|\bchalta hoon\b|\bchalti hoon\b",
     lambda: random.choice(["Bye bhai, milte hain 👋", "Chalo phir, take care"])),
]


def get_local_reply(text: str):
    t = text.lower().strip()
    for pattern, responder in LOCAL_RULES:
        if _re.search(pattern, t):
            return responder()
    return None


def get_gemini_reply(user_id: int, incoming_text: str) -> str:
    try:
        contents = []
        for m in conversation_memory[user_id]:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["text"]}]})
        contents.append({"role": "user", "parts": [{"text": incoming_text}]})

        system_text = GEMINI_SYSTEM_PROMPT + "\n\n" + get_time_context()
        payload = {"system_instruction": {"parts": [{"text": system_text}]}, "contents": contents}
        resp = requests.post(GEMINI_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini call fail, static message fallback: {e}")
        return AUTO_REPLY_MESSAGE


async def send_typed_reply(event, sender, reply_text: str):
    parts = [p.strip() for p in reply_text.split("|||") if p.strip()] or [reply_text]
    async with client.action(sender, "typing"):
        for i, part in enumerate(parts):
            typing_time = min(len(part) * 0.05, 4) + random.uniform(0.5, 1.5)
            await asyncio.sleep(typing_time)
            await event.reply(part)
            if i < len(parts) - 1:
                await asyncio.sleep(random.uniform(0.8, 2.0))


MEDIA_ACK = {
    "photo": "Photo mil gayi, dekh kar batata hoon 👍",
    "video": "Video mil gayi, dekhta hoon jaldi",
    "voice": "Voice message mila, sunkar reply karunga 🙏",
    "sticker": "😄",
    "document": "File mil gayi, check karta hoon",
}


def detect_media_type(event) -> str:
    if event.photo:
        return "photo"
    if event.voice:
        return "voice"
    if event.sticker:
        return "sticker"
    if event.video:
        return "video"
    if event.document:
        return "document"
    return ""


# ==== OWNER CONTROL: Saved Messages me /pause aur /resume ====
@client.on(events.NewMessage(outgoing=True))
async def owner_control(event):
    if not event.is_private:
        return
    me = await client.get_me()
    if event.chat_id != me.id:
        return  # sirf apni Saved Messages me command chalega

    text = (event.raw_text or "").strip().lower()
    if text == "/pause":
        bot_paused["value"] = True
        if use_mongo:
            mongo_db.state.update_one({"_id": "pause"}, {"$set": {"value": True}}, upsert=True)
        await event.reply("Bot pause ho gaya. Resume karne ke liye /resume bhejo.")
    elif text == "/resume":
        bot_paused["value"] = False
        if use_mongo:
            mongo_db.state.update_one({"_id": "pause"}, {"$set": {"value": False}}, upsert=True)
        await event.reply("Bot wapas chalu ho gaya.")


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_private or event.out:
        return
    if bot_paused["value"]:
        return

    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    user_id = sender.id
    if user_id in blocked_users:
        return

    is_whitelisted = user_id in WHITELIST_USER_IDS
    text = event.raw_text or ""

    # Naya user hai to notify karo (Saved Messages me)
    if NOTIFY_NEW_USER and user_id not in seen_users:
        seen_users.add(user_id)
        persist_seen(user_id)
        try:
            name = getattr(sender, "first_name", "Unknown")
            await client.send_message("me", f"🆕 Naya user pehli baar message kar raha hai: {name} (id: {user_id})")
        except Exception:
            pass

    daily_stats["count"] += 1
    daily_stats["users"].add(user_id)

    # Media handling -- text nahi hai to media type ke hisab se fixed ack
    media_type = detect_media_type(event)
    if media_type and not text:
        now = time.time()
        if not (is_whitelisted and VIP_SKIP_COOLDOWN):
            if user_id in last_replied and (now - last_replied[user_id]) < COOLDOWN:
                return
        await asyncio.sleep(random.uniform(2, 6))
        await send_typed_reply(event, sender, MEDIA_ACK.get(media_type, "Mil gaya, dekhta hoon"))
        last_replied[user_id] = now
        return

    # Abuse check
    if is_abusive(text):
        if await handle_abuse_and_block(user_id):
            return

    # Link/spam filter -- naya (pehli baar dikha) user agar seedha link bheje, ignore karo (likely spam)
    if URL_REGEX.search(text) and not is_whitelisted and user_id not in conversation_memory:
        log.info(f"Naye user {user_id} se link mila, spam maan kar skip kar rahe hain")
        return

    # DND / silent mode
    if DND_MODE == "silent" and is_dnd_time() and not is_whitelisted:
        return

    # Cooldown -- VIP whitelist chaho to cooldown skip kar sakta hai
    now = time.time()
    if not (is_whitelisted and VIP_SKIP_COOLDOWN):
        if user_id in last_replied and (now - last_replied[user_id]) < COOLDOWN:
            return

    if use_mongo and not conversation_memory[user_id]:
        load_memory_from_db(user_id)

    # Keyword-based instant reply (Gemini call skip)
    keyword_reply = check_keyword_response(text)
    local_reply = get_local_reply(text) if not keyword_reply else None

    if keyword_reply:
        reply_text = keyword_reply
    elif local_reply:
        reply_text = local_reply  # Gemini call hi nahi hui, quota bachi
    elif USE_GEMINI and GEMINI_API_KEY:
        reply_text = get_gemini_reply(user_id, text)
    else:
        reply_text = AUTO_REPLY_MESSAGE

    await asyncio.sleep(random.uniform(2, 8))
    await send_typed_reply(event, sender, reply_text)

    add_to_memory(user_id, "user", text)
    add_to_memory(user_id, "assistant", reply_text)
    last_replied[user_id] = now
    log.info(f"Auto-reply sent -> {getattr(sender, 'first_name', 'Unknown')} ({user_id})")


async def daily_summary_loop():
    last_sent_date = None
    while True:
        now = datetime.now()
        if DAILY_SUMMARY_ENABLED and now.hour == DAILY_SUMMARY_HOUR and last_sent_date != now.date():
            try:
                msg = f"📊 Aaj ka summary: {daily_stats['count']} messages, {len(daily_stats['users'])} alag logon se"
                await client.send_message("me", msg)
                last_sent_date = now.date()
                daily_stats["count"] = 0
                daily_stats["users"] = set()
            except Exception as e:
                log.warning(f"Daily summary bhejne me error: {e}")
        await asyncio.sleep(60)


class _HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthCheckHandler)
    log.info(f"Dummy health-check server chalu hua port {port} par")
    server.serve_forever()


async def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    load_persisted_state()
    log.info("Bot start ho raha hai...")
    await client.start()
    log.info("Bot chalu ho gaya, messages sunn raha hai.")
    asyncio.create_task(daily_summary_loop())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
                                      
