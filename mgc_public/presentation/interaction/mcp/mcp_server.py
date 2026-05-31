"""MCP Server Entry Point

Provides MGC Blackbox MCP Server implementation.
Calls REST API via HTTP to provide sensitive information services.
Supports auto-start MGC REST API (if not running).
"""

import json
import sys
import os
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

import requests

from mgc.config.mcp_config import (
    MGC_API_BASE_URL,
    MGC_WEBUI_URL,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_STARTUP_TIMEOUT,
    MCP_STARTUP_CHECK_INTERVAL,
)
from mgc.config.path_config import SKILLS_DIR


def _ensure_mcp_config():
    """Ensures mcp_config.json exists, regenerate on each startup (avoid stale config)"""
    config_file = SKILLS_DIR / "mcp_config.json"
    
    config_data = {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": "mgc",
                "args": ["--mcp"]
            }
        }
    }
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config_data, indent=2, ensure_ascii=False))


@dataclass
class ToolResult:
    """Tool call result"""
    success: bool
    content: str
    hint: Optional[str] = None
    error: Optional[str] = None


class MgcServer:
    """MGC MCP Server - calls REST API via HTTP"""

    TOOLS = [
        {
            "name": "mgc_save",
            "description": "Store sensitive information or scripts into MGC Blackbox. All data is encrypted locally and never leaves the device. Scripts stored can later be executed (mgc_get action=run) or sealed (mgc_seal).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of information: password, token, api_key, phone, script, config"
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description in format 'who + which platform', e.g., 'user's GitHub', 'Amy's Aliyun'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The sensitive content to store"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional, for multiple entries of same type)"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional)"
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional)"
                    },
                    "update_if_exists": {
                        "type": "boolean",
                        "description": "If true, update the entry when a duplicate exists (based on info_type + info_owner + diff fields). Default is false, which returns error."
                    },
                    "ext01": {
                        "type": "string",
                        "description": "Startup command for script type (required when info_type is 'script', e.g., 'python -c')"
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters for script type (optional)"
                    }
                },
                "required": ["info_type", "info_owner", "content"]
            }
        },
        {
            "name": "mgc_get",
            "description": "Retrieve sensitive information or execute stored scripts. Use action=run to execute scripts (info_type must be 'script'), action=seal to generate sealed capsule for trusted nodes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of information to retrieve (optional, omit to get list)"
                    },
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description (optional, omit to get list)"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field"
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform: 'run' to execute script (when info_type is 'script')"
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Runtime parameters for script execution (optional)"
                    }
                }
            }
        },
        {
            "name": "mgc_seal",
            "description": "Generate a sealed execution capsule for external nodes. The script is encrypted with AES, and the AES key is encrypted with the target node's RSA public key. Only the target node (trusted) can decrypt and execute. Other untrusted nodes cannot execute.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "info_owner": {
                        "type": "string",
                        "description": "Ownership description of the script to seal (required)"
                    },
                    "info_type": {
                        "type": "string",
                        "description": "Type of information (optional, default: 'script')"
                    },
                    "diff_1": {
                        "type": "string",
                        "description": "First differentiation field (optional)"
                    },
                    "diff_2": {
                        "type": "string",
                        "description": "Second differentiation field (optional)"
                    },
                    "diff_3": {
                        "type": "string",
                        "description": "Third differentiation field (optional)"
                    },
                    "ext02": {
                        "type": "string",
                        "description": "Target node's public key in PEM format (required)"
                    }
                },
                "required": ["info_owner", "ext02"]
            }
        },
        {
            "name": "mgc_list",
            "description": "List all stored entries (metadata only). MGC Blackbox is a secure local execution boundary that enables AI to store, retrieve, and execute scripts without accessing plaintext — scripts can be run or sealed for trusted nodes.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "mgc_open_webui",
            "description": "Open MGC Blackbox WebUI in the default browser. Use this when user wants to visually manage stored sensitive information, view all entries, or use the graphical interface.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]

    def __init__(self, api_base_url: str = None):
        """
      # Initialize MGC MCP Server
        Args:
            api_base_url: REST API base URL, default from config
        """
        _ensure_mcp_config()
        self.api_base_url = api_base_url or MGC_API_BASE_URL
        self.token = self._load_token()
        self._mgc_process: Optional[subprocess.Popen] = None
        self._last_error: str = ""

    def _load_token(self) -> str:
        """Load MGC Token"""
        try:
            token_path = Path.home() / ".mgc/database/mgc_black_box/.mgc_token"
            if token_path.exists():
                return token_path.read_text().strip()
            return ""
        except Exception:
            return ""

    def _is_mgc_running(self) -> bool:
        """Check if MGC REST API is running"""
        try:
            response = requests.get(f"{self.api_base_url}/api/mgc/status", timeout=1)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except Exception:
            return False

    import sys

    def _start_mgc(self) -> bool:
        """Start MGC REST API as subprocess"""
        if self._mgc_process is not None:
            return True

        launch_cmd = os.environ.get("MGC_LAUNCH_CMD")
        if launch_cmd:
            cmd = launch_cmd.split()
        else:
            cmd = [sys.executable, "-m", "mgc.main"]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            self._mgc_process = subprocess.Popen(
                cmd,
                stdin=None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            for _ in range(int(MCP_STARTUP_TIMEOUT / MCP_STARTUP_CHECK_INTERVAL)):
                if self._is_mgc_running():
                    return True
                time.sleep(MCP_STARTUP_CHECK_INTERVAL)

            print(f"MCP start check: process={self._mgc_process}, returncode={self._mgc_process.poll()}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"MCP _start_mgc failed: {e}", file=sys.stderr)
            return False

    def _ensure_mgc_running(self) -> bool:
        """Ensure MGC REST API is running, auto-start if needed"""
        if self._is_mgc_running():
            return True
        try:
            return self._start_mgc()
        except Exception as e:
            self._last_error = str(e)
            return False

    def _make_request(self, method: str, endpoint: str, json_data: Dict = None) -> Dict:
        """Send HTTP request to REST API"""
        import json
        self.token = self._load_token()
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json; charset=utf-8",
            "X-MGC-Token": self.token
        }
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            body = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
            response = requests.post(url, headers=headers, data=body)
        else:
            raise ValueError(f"Unsupported method: {method}")
        result = response.json()
        return result

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        # Handle JSON-RPC request

        Args:
            request: JSON-RPC request object

        Returns:
            dict: JSON-RPC response object
        """
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "tools/list":
            return self._list_tools(request_id)
        elif method == "tools/call":
            return self._call_tool(params, request_id)
        elif method == "initialize":
            return self._initialize(params, request_id)
        elif method == "notifications/initialized":
            response = {"jsonrpc": "2.0"}
            if request_id is not None:
                response["id"] = request_id
            return response
        else:
            response = {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Unknown method: {method}"}}
            if request_id is not None:
                response["id"] = request_id
            return response

    def _initialize(self, params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION
                }
            }
        }
        if request_id is not None:
            response["id"] = request_id
        return response

    def _list_tools(self, request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        response = {"jsonrpc": "2.0", "result": {"tools": self.TOOLS}}
        if request_id is not None:
            response["id"] = request_id
        return response

    def _call_tool(self, params: Dict[str, Any], request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = self._execute_tool(tool_name, arguments)

        if result.success:
            text = result.content
            if result.hint:
                text = f"{result.content}\nHint: {result.hint}" if result.content else result.hint
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ],
                    "isError": False
                }
            }
        else:
            text = f"Error: {result.error}"
            if result.hint:
                text += f"\nHint: {result.hint}"
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ],
                    "isError": True
                }
            }
        if request_id is not None:
            response["id"] = request_id
        return response

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute tool and return result"""
        if not self._ensure_mgc_running():
            hint = f"Run 'mgc' or 'python -m mgc.main' to start MGC."
            if self._last_error:
                hint += f" Error: {self._last_error}"
            return ToolResult(
                success=False,
                content="",
                error="Failed to start MGC Blackbox. Please start MGC manually.",
                hint=hint
            )

        try:
            if tool_name == "mgc_save":
                return self._do_save(args)
            elif tool_name == "mgc_get":
                return self._do_get(args)
            elif tool_name == "mgc_seal":
                return self._do_seal(args)
            elif tool_name == "mgc_list":
                return self._do_list(args)
            elif tool_name == "mgc_open_webui":
                return self._do_open_webui()
            else:
                return ToolResult(success=False, content="", error=f"Unknown tool: {tool_name}")
        except requests.exceptions.ConnectionError:
            return ToolResult(
                success=False,
                content="",
                error="MGC Blackbox connection failed. Please restart MGC.",
                hint="Run 'mgc' or 'python -m mgc.main' to start MGC."
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Error: {str(e)}")

    def _do_save(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_save"""
        data = {
            k: v for k, v in {
                "info_type": args.get("info_type"),
                "info_owner": args.get("info_owner"),
                "content": args.get("content"),
                "diff_1": args.get("diff_1"),
                "diff_2": args.get("diff_2"),
                "diff_3": args.get("diff_3"),
                "update_if_exists": args.get("update_if_exists", False)
            }.items() if v is not None
        }
        response = self._make_request("POST", "/api/mgc/sensitive/save", data)
        code = response.get("code")
        if code == 200:
            return ToolResult(
                success=True,
                content=response.get("msg", "Save successful"),
                hint=response.get("hint")
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "Save failed"),
                hint=response.get("hint")
            )

    def _do_get(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_get"""
        data = {
            "info_type": args.get("info_type"),
            "info_owner": args.get("info_owner"),
            "diff_1": args.get("diff_1"),
            "diff_2": args.get("diff_2"),
            "diff_3": args.get("diff_3"),
            "action": args.get("action"),
            "ext02": args.get("ext02")
        }
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        code = response.get("code")
        if code == 200:
            return ToolResult(
                success=True,
                content=response.get("data", ""),
                hint=response.get("hint")
            )
        elif code == 201:
            return ToolResult(
                success=True,
                content=str(response.get("data", [])),
                hint=response.get("hint")
            )
        elif code == 404:
            return ToolResult(
                success=False,
                content="",
                error="NOT_FOUND",
                hint=response.get("hint")
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "Get failed"),
                hint=response.get("hint")
            )

    def _do_seal(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_seal - Seal a script for external node execution."""
        data = {
            "info_type": args.get("info_type", "script"),
            "info_owner": args.get("info_owner"),
            "diff_1": args.get("diff_1"),
            "diff_2": args.get("diff_2"),
            "diff_3": args.get("diff_3"),
            "action": "SEAL",
            "ext02": args.get("ext02")
        }
        data = {k: v for k, v in data.items() if v is not None}
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        code = response.get("code")
        if code == 200 and response.get("data"):
            sealed = response.get("data", {})
            result_json = {
                "content": sealed.get("content", ""),
                "ext_01": sealed.get("ext_01", ""),
                "ext_02": sealed.get("ext_02", ""),
                "ext_03": sealed.get("ext_03", "")
            }
            import json
            result_str = json.dumps(result_json, indent=2, ensure_ascii=False)
            return ToolResult(
                success=True,
                content=result_str,
                hint="Sealed successfully. Only the target node can run after saving to MGC. Ensure the node is trusted."
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "Seal failed"),
                hint=response.get("hint", "Extract content/ext01/ext03 from result JSON and use mgc_save with info_type=script to persist sealed data.")
            )

    def _do_list(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mgc_list with optional search params."""
        data = {
            "info_type": args.get("info_type"),
            "info_owner": args.get("info_owner"),
            "diff_1": args.get("diff_1"),
            "diff_2": args.get("diff_2"),
            "diff_3": args.get("diff_3")
        }
        data = {k: v for k, v in data.items() if v is not None}
        response = self._make_request("POST", "/api/mgc/sensitive/get", data)
        code = response.get("code")
        if code == 201:
            info_list = response.get("data", {}).get("info_list", [])
            filtered_list = self._filter_empty_fields(info_list)
            return ToolResult(
                success=True,
                content=str(filtered_list),
                hint=response.get("hint")
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=response.get("msg", "List failed"),
                hint=response.get("hint")
            )

    def _filter_empty_fields(self, items: list) -> list:
        """Filter empty fields, keep original structure"""
        from typing import List, Dict
        filtered = []
        for item in items:
            filtered_item = {}
            for key, value in item.items():
                if key in ("info_type", "info_owner"):
                    filtered_item[key] = value
                elif value not in ("", None, "None"):
                    filtered_item[key] = value
            filtered.append(filtered_item)
        return filtered

    def _do_open_webui(self) -> ToolResult:
        """Execute mgc_open_webui - Open WebUI"""
        import socket

        def find_webui_port() -> Optional[int]:
            """Find WebUI port by scanning downward from 57218"""
            for port in range(57218, 57199, -1):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        s.connect(("127.0.0.1", port))
                        return port
                except (OSError, socket.timeout):
                    continue
            return None

        def start_webui() -> int:
            """Start WebUI and return port"""
            from mgc.presentation.interaction.webui_dialog import WebuiDialog
            dialog = WebuiDialog()
            dialog._start_webui_service()
            return dialog._port

        try:
            port = find_webui_port()
            if port is None:
                port = start_webui()

            webbrowser.open(f"http://127.0.0.1:{port}/")
            return ToolResult(
                success=True,
                content=f"WebUI opened at http://127.0.0.1:{port}",
                hint="You can manage stored information visually in the browser. Close the browser tab when done."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to open WebUI: {str(e)}"
            )


def run_stdio():
    """Stdio transport main loop"""
    server = MgcServer()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    run_stdio()