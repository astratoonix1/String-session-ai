"""
STEP 1: Yeh script pehle ek baar chalao — isse aapka STRING SESSION milega.
Iske liye phone number + OTP (aur agar 2FA on hai to password) dena hoga.

Install: pip install telethon
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# my.telegram.org se API_ID aur API_HASH lo (free, apne phone number se login karke)
API_ID = 12345678          # <-- yahan apna api_id daalo
API_HASH = "your_api_hash"  # <-- yahan apna api_hash daalo

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n=== Aapka STRING SESSION (isse kisi ko mat dena, yeh aapke account ki full key hai) ===\n")
    print(client.session.save())
    print("\n=== Ise copy karke bot.py file me STRING_SESSION variable me daalo ===\n")
  
