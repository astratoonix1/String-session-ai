# Telegram Auto-Reply Userbot

Apne personal Telegram account (string session) se chalne wala auto-reply bot. Jab bhi koi aapko private DM karega, yeh automatically reply karega — groups, channels aur bots ko ignore karta hai.

## Features

- Sirf **private DM** par reply karta hai (group/channel skip)
- **Cooldown system** — same user ko baar-baar spam reply nahi karta
- **Bots ko ignore** karta hai
- Optional **Gemini AI** (`gemini-3.6-flash`) integration — chahe to fixed message bheje, chahe to AI se dynamic smart reply generate kare
- Sab kuch **Environment Variables** se configure hota hai — code me kuch hardcode nahi
- Render pe **Docker** ke through deploy hota hai

## Files

| File | Kaam |
|---|---|
| `bot.py` | Main bot — yeh hi Render pe chalega |
| `generate_session.py` | Sirf **local pe ek baar** chalane wali script, isse STRING_SESSION milta hai. Isko repo/Render pe daalna zaroori nahi |
| `Dockerfile` | Render ko batata hai container kaise banaye |
| `requirements.txt` | Python dependencies (telethon, requests) |
| `README.md` | Yeh file |

## Setup — Step by Step

### 1. Telegram API credentials lo
- https://my.telegram.org par apne phone number se login karo
- **API Development Tools** me jaake ek app banao
- `api_id` aur `api_hash` mil jayenge — yeh safe rakhna

### 2. String Session generate karo (sirf local pe, ek baar)
```bash
pip install telethon
python generate_session.py
```
- API_ID aur API_HASH file me daalkar chalao
- Phone number + OTP (aur agar 2FA on hai to password) dena hoga
- Ek lambi string milegi — **yeh aapke account ki full key hai, kisi se share mat karna**

### 3. GitHub repo banao
Sirf yeh 3 files repo me daalo:
```
your-repo/
├── Dockerfile
├── requirements.txt
└── bot.py
```
`generate_session.py` repo me mat daalo — sirf local use ke liye hai.

### 4. Render pe deploy karo
1. Render dashboard → **New → Background Worker** (recommended — port ki zaroorat nahi padti)
   - Agar Web Service banaya hai to bhi chalega, code me dummy health-check server already hai jo port issue solve karta hai
2. GitHub repo connect karo
3. Environment = **Docker** select karo (Dockerfile auto-detect hoga)
4. Neeche diye Environment Variables set karo
5. Deploy karo

### 5. Environment Variables (Render → Environment tab)

| Key | Value | Zaroori? |
|---|---|---|
| `API_ID` | my.telegram.org se | ✅ Haan |
| `API_HASH` | my.telegram.org se | ✅ Haan |
| `STRING_SESSION` | generate_session.py se mila string | ✅ Haan |
| `AUTO_REPLY_MESSAGE` | apna custom fixed message | ❌ Optional (default hai) |
| `COOLDOWN_SECONDS` | e.g. `1800` (30 min) | ❌ Optional (default 1800) |
| `USE_GEMINI` | `true` ya `false` | ❌ Optional (default false) |
| `GEMINI_API_KEY` | aistudio.google.com se | ❌ sirf agar USE_GEMINI=true |
| `GEMINI_MODEL` | `gemini-3.6-flash` | ❌ Optional (already default) |
| `PORT` | Render khud set karta hai | ❌ Render automatically deta hai (sirf Web Service type me) |

## USE_GEMINI kaise kaam karta hai

- **`USE_GEMINI=false`** (ya set hi nahi kiya) → bot hamesha `AUTO_REPLY_MESSAGE` wala fixed message bhejega, chahe sender kuch bhi likhe
- **`USE_GEMINI=true`** + `GEMINI_API_KEY` diya → bot Gemini AI se sender ke message ke context ke hisab se dynamic Hinglish reply generate karega

## Known Risks

- **Telegram ToS**: String session wala approach ek "userbot" hai (personal account ka automation), official Bot API nahi. Bahut zyada/fast automated replies se Telegram spam-detect kar sakta hai
- **Account limit ka chance**: Rare cases me heavy automated activity se account temporarily restrict ho sakta hai — isliye cooldown zaroor rakha gaya hai
- **STRING_SESSION security**: Yeh password se bhi zyada sensitive hai (2FA bhi bypass karta hai) — kabhi GitHub public repo ya kisi ke saath share mat karna
- **Gemini dependency**: Agar API fail/rate-limited ho to bot automatically static message pe fallback kar jata hai — crash nahi hoga

## Troubleshooting

**"No open ports detected"**
- Service ko **Background Worker** type se banao, port ki zaroorat khatam ho jayegi
- Ya current code me dummy HTTP server already hai jo `PORT` env var pe bind karta hai — Web Service type me bhi chal jana chahiye

**AttributeError ya koi Python error deploy logs me**
- Confirm karo GitHub repo me **latest** `bot.py` push hua hai
- Render dashboard → **Manual Deploy → Deploy latest commit** dabao (auto-deploy off ho sakta hai)
- Naye logs ka timestamp check karo, purana cached log nahi

**Bot reply nahi kar raha**
- Environment Variables sahi se set hain ki nahi check karo (especially STRING_SESSION poora copy hua ki nahi, beech me kat to nahi gaya)
- Render logs me "Bot chalu ho gaya, messages sunn raha hai" line dikhni chahiye — agar nahi dikh rahi to bot start hi nahi hua
- 
