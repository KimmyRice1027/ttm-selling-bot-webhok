# ttm-selling-bot-webhok

This repository contains a minimal Telegram webhook-based bot (FastAPI) to accept orders for MLBB (dia) and PUBG (UC).

Features
- FastAPI app that accepts Telegram updates via /webhook
- Simple /start and /buy command handling
- Orders stored in a local SQLite database (orders.db)
- set_webhook helper script

Quickstart (local, using ngrok)
1) Create a virtualenv and install dependencies

   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2) Create .env from .env.example and set TELEGRAM_BOT_TOKEN and optionally OWNER_CHAT_ID

3) Run the app

   uvicorn webhook_app:app --host 0.0.0.0 --port 8000

4) Expose to the internet (ngrok example)

   ngrok http 8000

   # copy the https URL that ngrok gives you, then run:
   TELEGRAM_BOT_TOKEN=... python set_webhook.py https://<your-ngrok-domain>

5) Send commands to your bot on Telegram
   - /start
   - /buy mlbb dia 100

Notes
- This is a minimal example. Do NOT store real secrets in the repo.
- For production: use HTTPS, a hosted DB (Postgres), implement payment integration (Stripe, etc.), and secure admin endpoints.
