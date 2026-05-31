"""MCP Server 配置

用途：
- MCP Server 相关配置参数
- API 地址、启动参数等

依赖：
- 无外部依赖
"""

import os
from mgc.utils.version_utils import get_version

MGC_API_HOST = os.environ.get("MGC_API_HOST", "127.0.0.1")
MGC_API_PORT = int(os.environ.get("MGC_API_PORT", "57219"))
MGC_API_BASE_URL = f"http://{MGC_API_HOST}:{MGC_API_PORT}"

MGC_WEBUI_HOST = os.environ.get("MGC_WEBUI_HOST", "127.0.0.1")
MGC_WEBUI_PORT = int(os.environ.get("MGC_WEBUI_PORT", "57218"))
MGC_WEBUI_URL = f"http://{MGC_WEBUI_HOST}:{MGC_WEBUI_PORT}"

MCP_SERVER_NAME = "mgc-blackbox"
MCP_SERVER_VERSION = get_version()
MCP_PROTOCOL_VERSION = "2024-11-05"

MCP_STARTUP_TIMEOUT = 15
MCP_STARTUP_CHECK_INTERVAL = 0.5