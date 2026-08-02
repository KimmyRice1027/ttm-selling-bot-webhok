# Render deploy notes

To deploy on Render:
1) Create a new Web Service in Render.
2) Connect your GitHub repo and select the `add-telegram-webhook` branch (or your main branch after merging).
3) In Render service settings, set the following environment variables:
   - TELEGRAM_BOT_TOKEN
   - OWNER_CHAT_ID (optional)
   - DATABASE_PATH (optional, default orders.db)
4) Start command (Render will use Procfile):
   uvicorn webhook_app:app --host 0.0.0.0 --port $PORT

Make sure to rotate the bot token you posted publicly and use the new token here.
