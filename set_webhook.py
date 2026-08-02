# set_webhook.py
# Usage: TELEGRAM_BOT_TOKEN=... python set_webhook.py https://your-host.example.com/webhook

import os
import sys
import requests

if len(sys.argv) < 2:
    print("Usage: python set_webhook.py https://your-host.example.com/webhook")
    sys.exit(1)

url = sys.argv[1].rstrip("/") + "/webhook"
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise RuntimeError("Please set TELEGRAM_BOT_TOKEN environment variable")

r = requests.get(f"https://api.telegram.org/bot{token}/setWebhook", params={"url": url})
print(r.status_code, r.text)
