r"""
Example: Send Slack Message Directly

Run this script to send Slack messages without AI.
Supports mock mode for testing without real Slack.
"""

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print("Error: requests required. Install: pip install requests")
    sys.exit(1)

# MGC API configuration
MGC_BASE_URL = "http://127.0.0.1:57219"
MGC_TOKEN_PATH = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")
DEFAULT_INFO_TYPE = "config"
DEFAULT_INFO_OWNER = "slack_bot"


def get_mgc_token():
    """Get MGC access token."""
    if not os.path.exists(MGC_TOKEN_PATH):
        return None
    try:
        with open(MGC_TOKEN_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except IOError:
        return None


def get_slack_config_from_mgc(token, info_type=None, info_owner=None):
    """Get Slack config from MGC."""
    info_type = info_type or DEFAULT_INFO_TYPE
    info_owner = info_owner or DEFAULT_INFO_OWNER

    try:
        resp = requests.post(
            f"{MGC_BASE_URL}/api/mgc/sensitive/get",
            headers={
                "X-MGC-Token": token,
                "Content-Type": "application/json"
            },
            json={
                "info_type": info_type,
                "info_owner": info_owner
            },
            timeout=30
        )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                data_field = data.get("data")
                if isinstance(data_field, str):
                    return json.loads(data_field)
                elif isinstance(data_field, dict):
                    content = data_field.get("content")
                    if content:
                        return json.loads(content)
        return None
    except requests.exceptions.RequestException:
        return None
    except json.JSONDecodeError:
        return None


def validate_slack_config(config):
    """Validate Slack config JSON format."""
    has_webhook = "webhook_url" in config and config["webhook_url"]
    has_token = "bot_token" in config and config["bot_token"]

    if not has_webhook and not has_token:
        return False, "At least one of webhook_url or bot_token is required"

    return True, ""


def send_via_webhook(webhook_url, text, channel=None,
                  username=None, icon_emoji=None):
    """Send message via Incoming Webhook."""
    payload = {"text": text}

    if channel:
        payload["channel"] = channel
    if username:
        payload["username"] = username
    if icon_emoji:
        payload["icon_emoji"] = icon_emoji

    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        if resp.status_code == 200:
            return True, "Message sent via webhook"
        else:
            return False, f"Webhook error: {resp.status_code}"
    except Exception as e:
        return False, str(e)


def send_via_api(bot_token, text, channel=None,
               username=None, icon_emoji=None):
    """Send message via Slack Bot API."""
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }

    target = channel or "#general"

    payload = {
        "text": text,
        "channel": target
    }

    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=30
        )

        if resp.status_code == 200:
            result = resp.json()
            if result.get("ok"):
                return True, "Message sent via Bot API"
            else:
                return False, f"API error: {result.get('error')}"
        else:
            return False, f"API error: {resp.status_code}"
    except Exception as e:
        return False, str(e)


def mock_test(text, channel, username, icon_emoji, config):
    """Mock test mode - validate without sending."""
    print(f"[MOCK] Text: {text}")
    print(f"[MOCK] Channel: {channel}")
    print(f"[MOCK] Username: {username}")
    print(f"[MOCK] Icon: {icon_emoji}")
    print(f"[MOCK] Config loaded: {bool(config)}")
    if config:
        has_webhook = "webhook_url" in config and config["webhook_url"]
        has_token = "bot_token" in config and config["bot_token"]
        print(f"[MOCK] Has webhook: {has_webhook}")
        print(f"[MOCK] Has bot_token: {has_token}")
    return True, "Mock test passed - MGC logic validated"


def main():
    parser = argparse.ArgumentParser(description="Send Slack message via MGC")
    parser.add_argument("--text", "-t", required=True, help="Message text")
    parser.add_argument("--channel", "-c", help="Target channel")
    parser.add_argument("--username", "-u", help="Custom username")
    parser.add_argument("--icon", "-i", help="Emoji icon (e.g., :robot:)")
    parser.add_argument("--mock", action="store_true", help="Mock test mode")
    parser.add_argument("--info-type", default=DEFAULT_INFO_TYPE, help="MGC info_type")
    parser.add_argument("--info-owner", default=DEFAULT_INFO_OWNER, help="MGC info_owner")
    args = parser.parse_args()

    # Input validation
    if not args.text or not args.text.strip():
        print("Error: Validation failed - 'text' cannot be empty")
        sys.exit(1)

    print("=" * 40)
    print("Secure Slack Bot")
    if args.mock:
        print("[MOCK MODE]")
    print("=" * 40)

    # Get token
    print("\n[1] Getting MGC token...")
    token = get_mgc_token()
    if token is None:
        print("Error: MGC error - Token file not found. Run 'mgc' to initialize.")
        sys.exit(1)
    print("OK")

    # Get config
    print("[2] Getting Slack config from MGC...")
    config = get_slack_config_from_mgc(token, args.info_type, args.info_owner)
    if config is None:
        print("Error: MGC error - Credentials not found. Store Slack config in MGC first.")
        sys.exit(1)
    print("OK")

    # Validate config
    is_valid, error_msg = validate_slack_config(config)
    if not is_valid:
        print(f"Error: MGC error - Invalid credentials format - {error_msg}")
        sys.exit(1)

    print(f"OK: config loaded")

    # Mock test or send
    target_channel = args.channel or config.get("default_channel")

    if args.mock:
        print("[3] Running mock test...")
        success, message = mock_test(
            args.text, target_channel,
            args.username, args.icon,
            config
        )
    else:
        print("[3] Sending message...")
        # Prefer webhook
        if "webhook_url" in config and config["webhook_url"]:
            success, message = send_via_webhook(
                config["webhook_url"],
                args.text,
                target_channel,
                args.username,
                args.icon
            )
        elif "bot_token" in config and config["bot_token"]:
            success, message = send_via_api(
                config["bot_token"],
                args.text,
                target_channel,
                args.username,
                args.icon
            )
        else:
            success, message = False, "No valid credentials"

    print("\n" + "=" * 40)
    if success:
        print(f"SUCCESS: {message}")
    else:
        print(f"FAILED: {message}")
        sys.exit(1)
    print("=" * 40)


if __name__ == "__main__":
    main()