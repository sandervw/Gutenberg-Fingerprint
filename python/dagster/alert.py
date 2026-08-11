# Failure alerts: POST to Cloudflare Email Sending REST API.

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "954c30f428e0a61f4c66e6a679f51ec0")
TOKEN_FILE = Path("~/.config/gufime/cf_token").expanduser()
ALERT_FROM = os.environ.get("GUFIME_ALERT_FROM", "alerts@gufime.com")
ALERT_TO = os.environ.get("GUFIME_ALERT_TO", "samvanwilligen@gmail.com")
ENDPOINT = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/email/sending/send"


def _token() -> str:
    # Env override first; else the shared box token file.
    return os.environ.get("CLOUDFLARE_API_TOKEN") or TOKEN_FILE.read_text().strip()


def send(subject: str, text: str) -> None:
    """Send one transactional alert via Cloudflare Email Sending."""
    payload = json.dumps(
        {
            "to": ALERT_TO,
            "from": {"address": ALERT_FROM, "name": "gufime pipeline"},
            "subject": subject,
            "text": text,
        }
    ).encode()
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"cloudflare email {error.code}: {error.read().decode()}") from error
    if not body.get("success"):
        raise RuntimeError(f"cloudflare email failed: {body.get('errors')}")
    print(f"alert sent -> {ALERT_TO}")


if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "gufime test alert"
    send("gufime pipeline: test alert", message)
