"""app.py shim: re-export Flask app at module path 'app' so existing
start command `gunicorn app:app` works.
"""

import os
from server.telegram_webhook import app

if __name__ == "__main__":
    # Respect PORT env var when run directly (useful for local testing or simple hosts)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
