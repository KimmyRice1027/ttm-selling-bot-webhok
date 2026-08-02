# Minimal FastAPI Telegram webhook bot for selling MLBB/PUBG dia/UC
# - Stores orders in a local SQLite database (orders.db)
# - Commands supported: /start, /buy <game> <item> <quantity>
# - Example: /buy mlbb dia 100

import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, Request
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # optional: admin chat id for notifications
DB_PATH = os.getenv("DATABASE_PATH", "orders.db")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Please set TELEGRAM_BOT_TOKEN environment variable")

BOT_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI()

# --- Database helpers ---

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            username TEXT,
            game TEXT,
            item TEXT,
            quantity INTEGER,
            status TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def create_order(chat_id: int, username: str, game: str, item: str, quantity: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO orders (chat_id, username, game, item, quantity, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (chat_id, username, game, item, quantity, "pending", created_at),
    )
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id


# initialize DB on startup
init_db()


# --- Telegram helpers ---
async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{BOT_API}/sendMessage", json={"chat_id": chat_id, "text": text})


async def notify_owner(text: str):
    if not OWNER_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{BOT_API}/sendMessage", json={"chat_id": int(OWNER_CHAT_ID), "text": text})
    except Exception:
        pass


# --- Webhook endpoint ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        # ignore other update types
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    username = from_user.get("username") or f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
    text = message.get("text", "").strip()

    if text.startswith("/start"):
        await send_message(chat_id, "ဟယ်လို! Dia/UC ရောင်းဝယ် Bot မှ ကြိုဆိုပါတယ်။\nသုံးစွဲနည်း - /buy <game> <item> <quantity>\nဥပမာ: /buy mlbb dia 100")
        return {"ok": True}

    if text.lower().startswith("/buy"):
        parts = text.split()
        # Expect: /buy <game> <item> <quantity>
        if len(parts) < 3:
            await send_message(chat_id, "အသုံးပြုပုံ: /buy <game> <item> <quantity>\nဥပမာ: /buy mlbb dia 100")
            return {"ok": True}
        game = parts[1].lower()
        item = parts[2].lower()
        qty = 1
        if len(parts) >= 4 and parts[3].isdigit():
            qty = int(parts[3])

        # Basic validation: allow known games
        if game not in ("mlbb", "pubg"):
            await send_message(chat_id, "ကျွန်တော်လက်ခံတဲ့ game မဟုတ်ပါ — 支持: mlbb, pubg")
            return {"ok": True}

        order_id = create_order(chat_id, username, game, item, qty)
        await send_message(
            chat_id,
            f"အော်ဒါ အောင်မြင်ပါသည်!\nOrder ID: {order_id}\nGame: {game}\nItem: {item}\nQuantity: {qty}\nStatus: pending\n\nကျေးဇူးပြု၍ ငွေပေးချေမှုကို ပြုလုပ်ပါ။ (ဒီနမူနာမှာ payment link မဖြည့်ထားပါ)",
        )
        # notify owner/admin
        await notify_owner(f"New order #{order_id} from @{username} ({chat_id}): {game} {item} x{qty}")
        return {"ok": True}

    # fallback
    await send_message(chat_id, "���သိသော command — /start သို့ /buy ကို စမ်းကြည့်ပါ။")
    return {"ok": True}
