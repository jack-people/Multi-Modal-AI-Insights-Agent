from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_tools.registry import register_tools
from mcp_tools.service import McpService


def create_mcp(include: Sequence[str] | None = None) -> tuple[FastMCP, dict[str, Callable[..., Any]]]:
    """include=None 注册全量工具（stdio / harness）；dsh 传 DSH_HTTP_TOOL_NAMES。"""
    mcp = FastMCP("multi-modal-ai-insights-agent", streamable_http_path="/")
    functions = register_tools(mcp, McpService(), include=include)
    return mcp, functions
