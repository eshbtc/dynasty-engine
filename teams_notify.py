# teams_notify.py – Simple helper for sending notifications to Microsoft Teams
import os, requests, json

def send_teams_notification(message: str) -> bool:
    """Send a notification to MS Teams via webhook URL in TEAMS_URL env var."""
    webhook_url = os.getenv("TEAMS_URL")
    if not webhook_url:
        print("[Teams Notify] TEAMS_URL not set in environment.")
        return False
    payload = {"text": message}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"[Teams Notify] Message sent successfully: {message}")
            return True
        else:
            print(f"[Teams Notify] Failed with status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[Teams Notify] Exception: {e}")
        return False

if __name__ == "__main__":
    # Test message
    send_teams_notification("✅ Dynasty Engine MS Teams notification test.")
