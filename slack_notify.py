# ------------------------------------------------------------------
# notify.py – one‑liner helper for Slack and Teams
# ------------------------------------------------------------------
import os, requests, json, datetime as dt

# Either Slack or Microsoft Teams webhook URLs
SLACK_URL = os.getenv("SLACK_WEBHOOK_URL")
TEAMS_URL = os.getenv("TEAMS_URL")


def _post(url: str, payload: dict):
    """Internal helper to POST JSON payload with basic error handling."""
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[Notify] Error posting to webhook: {e}")


def slack(msg: str):
    """Send a notification to Teams if TEAMS_URL set, otherwise Slack.

    Existing call sites keep using sn.slack(msg) for compatibility.
    """
    if TEAMS_URL:
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": "Dynasty Engine Alert",
            "themeColor": "0076D7",
            "title": f"Dynasty Engine – {dt.datetime.utcnow():%Y-%m-%d %H:%M UTC}",
            "text": msg,
        }
        _post(TEAMS_URL, card)
    elif SLACK_URL:
        _post(SLACK_URL, {"text": msg})
    else:
        print(f"[Notify] {msg}")
