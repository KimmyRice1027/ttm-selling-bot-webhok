#!/usr/bin/env python3
"""
Simple Telegram webhook echo bot using Flask.

Environment variables expected:
- TELEGRAM_BOT_TOKEN (required to send replies)
- TELEGRAM_WEBHOOK_SECRET (optional) : if set, will verify incoming requests using
  the "X-Telegram-Bot-Api-Secret-Token" header (set this when calling setWebhook).
- PORT (optional, default 5000)

Usage:
- Set TELEGRAM_BOT_TOKEN and optionally TELEGRAM_WEBHOOK_SECRET in your environment.
- Deploy this Flask app and set the Telegram webhook to the URL pointing at
  /telegram/webhook or /telegram/webhook/<secret> depending on how you want to pass
  the secret. Example:
    curl -F "url=https://example.com/telegram/webhook" -F "secret_token=MYSECRET" \
      https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook

This file is intentionally small and focuses on echo functionality. Expand it with
command handling, persistence, and other features as needed.
"""

import os
import logging
from flask import Flask, request, abort, jsonify
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-echo")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

if not BOT_TOKEN:
    logger.warning("Environment variable TELEGRAM_BOT_TOKEN is not set. The bot won't be able to send messages.")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def verify_telegram_secret(req) -> bool:
    """
    If WEBHOOK_SECRET is set, verify that Telegram sent the same value in
    the X-Telegram-Bot-Api-Secret-Token header.
    """
    if not WEBHOOK_SECRET:
        return True
    header = req.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return header == WEBHOOK_SECRET


def send_message(chat_id: int, text: str):
    if not BOT_TOKEN:
        logger.error("BOT token not configured; cannot send message.")
        return False
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        return True
    except Exception as e:
        logger.exception("Failed to send message: %s", e)
        return False


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook_no_token():
    # Accepts requests when you use the secret token header approach.
    if not verify_telegram_secret(request):
        logger.warning("Invalid webhook secret header")
        abort(401)
    return handle_update(request.get_json(silent=True) or {})


@app.route("/telegram/webhook/<path:maybe_secret>", methods=["POST"])
def telegram_webhook_with_path(maybe_secret: str):
    # Optional: allow secret in URL path if you prefer (e.g., /telegram/webhook/MYSECRET)
    if WEBHOOK_SECRET:
        # If WEBHOOK_SECRET configured, require either header OR matching path token
        header_ok = verify_telegram_secret(request)
        path_ok = (maybe_secret == WEBHOOK_SECRET)
        if not (header_ok or path_ok):
            logger.warning("Invalid webhook secret (header and path failed)")
            abort(401)
    # If no WEBHOOK_SECRET configured, accept requests to the path (still not secure)
    return handle_update(request.get_json(silent=True) or {})


def handle_update(update: dict):
    logger.info("Received update: %s", update)
    # Handle incoming message (normal messages are under 'message')
    message = update.get("message") or update.get("edited_message")
    if not message:
        logger.debug("No message found in update; ignoring.")
        return jsonify({"ok": True}), 200

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text")

    if not chat_id or text is None:
        logger.debug("Message missing chat_id or text; ignoring.")
        return jsonify({"ok": True}), 200

    # Echo logic: send back exactly the same text (you can change this)
    reply_text = text  # or f"Echo: {text}"
    success = send_message(chat_id, reply_text)
    if success:
        return jsonify({"ok": True}), 200
    else:
        return jsonify({"ok": False}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
