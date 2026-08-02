import os
import sqlite3
import json
from datetime import datetime
from fastapi import FastAPI, Request
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # admin chat id
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


def get_order(order_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, username, game, item, quantity, status, created_at FROM orders WHERE id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    keys = ["id", "chat_id", "username", "game", "item", "quantity", "status", "created_at"]
    return dict(zip(keys, row))


def update_order_status(order_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def list_orders(limit: int = 50, status: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute(
            "SELECT id, chat_id, username, game, item, quantity, status, created_at FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        c.execute(
            "SELECT id, chat_id, username, game, item, quantity, status, created_at FROM orders ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    rows = c.fetchall()
    conn.close()
    keys = ["id", "chat_id", "username", "game", "item", "quantity", "status", "created_at"]
    return [dict(zip(keys, r)) for r in rows]


# initialize DB on startup
init_db()


# --- Telegram helpers ---
async def telegram_api(method: str, payload: dict):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BOT_API}/{method}", json=payload)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "status_code": r.status_code, "text": r.text}


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await telegram_api("sendMessage", payload)


async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict | None = None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await telegram_api("editMessageText", payload)


async def answer_callback(callback_query_id: str, text: str | None = None, show_alert: bool = False):
    payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    return await telegram_api("answerCallbackQuery", payload)


async def notify_owner(text: str):
    if not OWNER_CHAT_ID:
        return
    try:
        await send_message(int(OWNER_CHAT_ID), text)
    except Exception:
        pass


# --- Utilities ---

def make_reply_markup(buttons: list[list[dict]]):
    return {"inline_keyboard": buttons}


def format_order(o: dict):
    return f"Order #{o['id']} — @{o.get('username') or ''}\nGame: {o['game']}\nItem: {o['item']} x{o['quantity']}\nStatus: {o['status']}\nCreated: {o['created_at']}"


# --- Webhook endpoint ---
@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()

    # Handle callback_query (button presses)
    callback = payload.get("callback_query")
    if callback:
        data = callback.get("data")
        callback_id = callback.get("id")
        from_user = callback.get("from", {})
        user_chat_id = from_user.get("id")
        message = callback.get("message")
        message_id = message.get("message_id") if message else None

        # data examples: confirm:123, cancel:123, admin_complete:123
        if data:
            parts = data.split(":")
            action = parts[0]
            order_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

            if action == "confirm" and order_id:
                o = get_order(order_id)
                if not o:
                    await answer_callback(callback_id, "Order not found", show_alert=True)
                elif o["chat_id"] != user_chat_id:
                    await answer_callback(callback_id, "You are not the owner of this order", show_alert=True)
                else:
                    update_order_status(order_id, "confirmed")
                    await answer_callback(callback_id, "Order confirmed. Please proceed to payment (not implemented).")
                    await edit_message_text(o["chat_id"], message_id, f"{format_order(get_order(order_id))}\n\nUser confirmed order.")
                    await notify_owner(f"Order #{order_id} confirmed by @{o.get('username')}")

            elif action == "cancel" and order_id:
                o = get_order(order_id)
                if not o:
                    await answer_callback(callback_id, "Order not found", show_alert=True)
                elif o["chat_id"] != user_chat_id and str(user_chat_id) != OWNER_CHAT_ID:
                    await answer_callback(callback_id, "Not allowed", show_alert=True)
                else:
                    update_order_status(order_id, "cancelled")
                    await answer_callback(callback_id, "Order cancelled.")
                    if message_id:
                        await edit_message_text(o["chat_id"], message_id, f"{format_order(get_order(order_id))}\n\nOrder cancelled.")
                    await notify_owner(f"Order #{order_id} cancelled by @{from_user.get('username')}")

            elif action == "admin_complete" and order_id:
                # only owner/admin can complete
                if not OWNER_CHAT_ID or int(user_chat_id) != int(OWNER_CHAT_ID):
                    await answer_callback(callback_id, "Only admin can perform this", show_alert=True)
                else:
                    update_order_status(order_id, "completed")
                    o = get_order(order_id)
                    await answer_callback(callback_id, "Marked as completed")
                    # notify buyer
                    await send_message(o["chat_id"], f"Your order #{order_id} has been completed. Thank you!")
                    await notify_owner(f"Order #{order_id} marked completed by admin")

            else:
                await answer_callback(callback_id, "Unknown action", show_alert=True)

        return {"ok": True}

    # Handle normal message updates
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    username = from_user.get("username") or f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
    text = message.get("text", "").strip()

    if text.startswith("/start"):
        await send_message(
            chat_id,
            "ဟယ်လို! Dia/UC ရောင်းဝယ် Bot မှ ကြိုဆိုပါတယ်။\nသုံးစွဲနည်း - /buy <game> <item> <quantity>\nဥပမာ: /buy mlbb dia 100",
        )
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

        if game not in ("mlbb", "pubg"):
            await send_message(chat_id, "ကျွန်တော်လက်ခံတဲ့ game မဟုတ်ပါ — supported: mlbb, pubg")
            return {"ok": True}

        order_id = create_order(chat_id, username, game, item, qty)
        text_msg = f"New order created:\nOrder ID: {order_id}\nGame: {game}\nItem: {item}\nQuantity: {qty}\nStatus: pending"

        # Inline buttons: Confirm, Cancel, (Pay placeholder)
        buttons = [
            [
                {"text": "Confirm Order", "callback_data": f"confirm:{order_id}"},
                {"text": "Cancel Order", "callback_data": f"cancel:{order_id}"},
            ],
            [
                {"text": "Pay (placeholder)", "url": "https://example.com/pay"}
            ]
        ]
        reply_markup = make_reply_markup(buttons)

        # send message with buttons
        r = await send_message(chat_id, text_msg, reply_markup=reply_markup)
        # notify owner/admin
        await notify_owner(f"New order #{order_id} from @{username} ({chat_id}): {game} {item} x{qty}")
        return {"ok": True}

    # Admin command: /orders
    if text.lower().startswith("/orders"):
        if not OWNER_CHAT_ID or int(chat_id) != int(OWNER_CHAT_ID):
            await send_message(chat_id, "Only admin can use /orders")
            return {"ok": True}
        # optional: /orders pending
        parts = text.split()
        status = parts[1].lower() if len(parts) >= 2 else None
        orders = list_orders(limit=20, status=status)
        if not orders:
            await send_message(chat_id, "No orders found")
            return {"ok": True}
        for o in orders:
            buttons = [[{"text": "Mark Completed", "callback_data": f"admin_complete:{o['id']}"}, {"text": "Cancel", "callback_data": f"cancel:{o['id']}"}]]
            await send_message(chat_id, format_order(o), reply_markup=make_reply_markup(buttons))
        return {"ok": True}

    # fallback
    await send_message(chat_id, "မသိတဲ့ command — /start သို့ /buy ကို စမ်းကြည့်ပါ။")
    return {"ok": True}
