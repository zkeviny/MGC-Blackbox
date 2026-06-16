r"""
MCP Server for Secure Slack Bot

This is the core skill file for Skill Store.
Defines MCP tools that AI can call to send Slack messages securely.
"""

import json
import os
from typing import Optional, List

# Third-party imports
try:
    import requests
except ImportError:
    raise ImportError("requests required: pip install requests")

try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError("fastmcp required: pip install fastmcp")

# MGC API configuration
MGC_BASE_URL = "http://127.0.0.1:57219"
MGC_TOKEN_PATH = os.path.expanduser("~/.mgc/database/mgc_black_box/.mgc_token")
DEFAULT_INFO_TYPE = "config"
DEFAULT_INFO_OWNER = "slack_bot"

# Create MCP server
mcp = FastMCP("SecureSlackBot")


def get_mgc_token() -> Optional[str]:
    """Get MGC access token."""
    if not os.path.exists(MGC_TOKEN_PATH):
        return None
    try:
        with open(MGC_TOKEN_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except IOError:
        return None


def get_slack_config_from_mgc(token: str, info_type: str = None,
                        info_owner: str = None) -> Optional[dict]:
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


def validate_slack_config(config: dict) -> tuple:
    """Validate Slack config JSON format.

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    has_webhook = "webhook_url" in config and config["webhook_url"]
    has_token = "bot_token" in config and config["bot_token"]

    if not has_webhook and not has_token:
        return False, "At least one of webhook_url or bot_token is required"

    return True, ""


def send_via_webhook(webhook_url: str, text: str, channel: str = None,
                username: str = None, icon_emoji: str = None) -> tuple:
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


def send_via_api(bot_token: str, text: str, channel: str = None,
               username: str = None, icon_emoji: str = None) -> tuple:
    """Send message via Slack Bot API."""
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }

    # Determine channel
    if channel:
        target = channel
    else:
        target = "#general"

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


@mcp.tool()
def send_slack_message(
    text: str,
    channel: str = None,
    username: str = None,
    icon_emoji: str = None,
    info_type: str = DEFAULT_INFO_TYPE,
    info_owner: str = DEFAULT_INFO_OWNER
) -> dict:
    """Send a message to Slack using MGC-stored credentials.

    Args:
        text: Message text.
        channel: Target channel (default: from config).
        username: Custom username.
        icon_emoji: Emoji icon (e.g., :robot:).
        info_type: MGC info_type (default: config).
        info_owner: MGC info_owner (default: slack_bot).

    Returns:
        dict with keys: success (bool), message (str).
    """
    # Input validation
    if not text or not text.strip():
        return {
            "success": False,
            "message": "Validation failed: 'text' cannot be empty"
        }

    # Get MGC token
    token = get_mgc_token()
    if token is None:
        return {
            "success": False,
            "message": "MGC error: Token file not found. Run 'mgc' to initialize."
        }

    # Get Slack config from MGC
    config = get_slack_config_from_mgc(token, info_type, info_owner)
    if config is None:
        return {
            "success": False,
            "message": "MGC error: Credentials not found. Store Slack config in MGC first."
        }

    # Validate config format
    is_valid, error_msg = validate_slack_config(config)
    if not is_valid:
        return {
            "success": False,
            "message": f"MGC error: Invalid credentials format - {error_msg}"
        }

    # Determine channel
    target_channel = channel or config.get("default_channel")

    # Send message (prefer webhook if available)
    if "webhook_url" in config and config["webhook_url"]:
        success, message = send_via_webhook(
            config["webhook_url"],
            text,
            target_channel,
            username,
            icon_emoji
        )
    elif "bot_token" in config and config["bot_token"]:
        success, message = send_via_api(
            config["bot_token"],
            text,
            target_channel,
            username,
            icon_emoji
        )
    else:
        success, message = False, "No valid credentials found"

    return {
        "success": success,
        "message": message
    }


if __name__ == "__main__":
    # Run as MCP server
    mcp.run()