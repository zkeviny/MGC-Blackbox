---
name: secure_slack_bot
description: Send Slack messages securely using MGC Blackbox. No plaintext credentials, no leaks.
version: 1.0.0
author: MirginCipher
license: MIT
category: Communication
---

# Zero‑Exposure Slack Sender (MGC Secure Edition)

This skill sends messages to Slack channels without exposing webhook URLs or bot tokens.  
All credentials are stored and retrieved securely from **MGC Blackbox**, ensuring zero plaintext secrets and zero accidental leaks.

---

## 🔧 Dependencies

### Prerequisites

- **MGC Blackbox installed and running**
- **Slack credentials stored in MGC**

Start MGC:

```bash
mgc
```

### MGC Service Information

| Item | Value |
|------|-------|
| Port | 57219 |
| Token Path | ~/.mgc/database/mgc_black_box/.mgc_token |
| Start Command | `mgc` |

### Slack Credentials JSON Format

```json
{
  "webhook_url": "https://hooks.slack.com/services/T.../B.../xxxx",
  "bot_token": "xoxb-...",
  "default_channel": "#general"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| webhook_url | No* | Slack Incoming Webhook URL |
| bot_token | No* | Bot User OAuth Token |
| default_channel | No | Default channel name |

\* At least **one** of `webhook_url` or `bot_token` must be provided.

---

## 🔐 Configuration

Store credentials in MGC:

```bash
mgc_save info_type=config info_owner=slack_bot < slack_config.json
```

> `info_type` and `info_owner` are identifiers you define yourself, used to retrieve encrypted data from MGC.

---

## ✅ Supported Functionality

- Send text messages via Webhook  
- Send text messages via Bot API  
- Custom username  
- Custom emoji icon  
- Default channel support  

## ❌ Not Supported

- Block Kit rich messages  
- File uploads  
- Thread replies  
- Channel listing  

---

# 🛠 MCP Tools

## **send_slack_message**

Send a Slack message using credentials stored in MGC.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| text | string | Yes | Message text |
| channel | string | No | Target channel |
| username | string | No | Custom bot name |
| icon_emoji | string | No | Emoji icon (e.g., `:robot:`) |
| info_type | string | No | MGC info_type (default: `config`) |
| info_owner | string | No | MGC info_owner (default: `slack_bot`) |

### Returns

```json
{
  "success": true,
  "message": "Message sent"
}
```

---

## 💬 Trigger Phrases

- "send to slack"
- "slack message"
- "post to slack"
- "slack notification"

---

# 📘 Examples

## Python (via MCP SDK)

```python
from mcp import MCPClient

client = MCPClient("http://localhost:57219")

result = client.call_tool("send_slack_message", {
    "text": "Deployment complete!",
    "channel": "#deployments",
    "username": "Deploy Bot",
    "icon_emoji": ":rocket:"
})

print(result)
```

## Direct Run

```bash
python example.py -t "Hello Slack"
python example.py -t "Hello" -c "#general"
```

---

# 🧪 Testing

Mock mode (no real Slack request):

```bash
python example.py -t "Test message" --mock
```

---

# 🛡 Security

- Credentials stored **locally only** in MGC  
- No plaintext secrets in code  
- No cloud upload  
- Credentials retrieved securely at runtime  
- No subprocess / exec / shell commands  

---

# 👤 Author

MirginCipher

# 📄 License

MIT
```

---