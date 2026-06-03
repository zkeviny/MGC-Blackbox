"""MCP Server 模块

提供 MGC Blackbox 的 MCP Server 实现
"""

from .mcp_server import MgcServer, run_stdio

__all__ = ["MgcServer", "run_stdio"]