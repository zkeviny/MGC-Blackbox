# Zero‑Exposure Slack Sender (MGC Secure Edition)

Send Slack messages safely without exposing webhook URLs or bot tokens.  
All credentials are stored locally in **MGC Blackbox**, ensuring zero plaintext secrets and zero accidental leaks.

---

## ✨ Features

- **Zero‑Exposure:** Slack credentials never appear in code or logs  
- **Local encryption:** Powered by MGC Blackbox secure vault  
- **Supports Webhook & Bot Token**  
- **CLI + MCP Tool** dual usage  
- **Mock mode** for development without real Slack

---

## 📦 Installation

Install MGC Blackbox:

```bash
pip install mgc-blackbox
mgc
```

Clone this skill:

```bash
git clone https://github.com/zkeviny/MGC-Blackbox
cd MGC-Blackbox/mgc_skill/secure_slack_bot
```

Run the MCP server:

```bash
python mcp_server.py
```

---

## 🔐 Store Slack Credentials in MGC

Create a JSON file:

```json
{
  "webhook_url": "https://hooks.slack.com/services/T.../B.../xxxx",
  "bot_token": "xoxb-...",
  "default_channel": "#general"
}
```

Store it securely:

```bash
mgc_save info_type=config info_owner=slack_bot < slack_config.json
```

> info_type and info_owner are identifiers you define yourself, used to retrieve encrypted data from MGC.

---

## 🚀 Usage

### ▶ Command Line

```bash
# Basic message
python example.py -t "Deployment complete!"

# Specify channel
python example.py -t "Deploy done" -c "#deployments"

# Custom username + icon
python example.py -t "Deploy done" -u "Deploy Bot" -i ":rocket:"

# Mock test (no real Slack request)
python example.py -t "Test" --mock
```

---

## 🛠 MCP Tool: `send_slack_message`

Example:

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

Tool parameters:

| Name        | Type   | Description |
|-------------|--------|-------------|
| text        | string | Message text |
| channel     | string | Slack channel (optional) |
| username    | string | Custom bot name (optional) |
| icon_emoji  | string | Emoji icon (optional) |

---

## 📁 Files

| File | Description |
|------|-------------|
| `README.md` | This file |
| `SKILL.md` | Skill documentation for AI clients |
| `mcp_server.py` | MCP server implementation |
| `example.py` | CLI demo script |

---

## 🔒 Security

- Credentials stored only in **local MGC Blackbox**
- No plaintext secrets in code or logs
- No cloud upload
- No subprocess / exec / shell usage
- Safe for AI automation workflows

---

## 📄 License

MIT  
Author: **MirginCipher**
```

---