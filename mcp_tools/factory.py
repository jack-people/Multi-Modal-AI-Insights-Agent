from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp_tools.registry import DSH_HTTP_TOOL_NAMES, register_tools
from mcp_tools.service import McpService


def create_mcp(
    *,
    include: Sequence[str] | None = None,
    service: McpService | None = None,
    name: str = "multi-modal-ai-insights-agent",
) -> tuple[Any, McpService, dict]:
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "缺少 mcp 依赖，请先安装：pip install 'mcp>=1.9,<2'\n"
            f"原始错误: {exc}"
        ) from exc

    svc = service or McpService()
    mcp = FastMCP(name, streamable_http_path="/", port=8001)
    functions = register_tools(mcp, svc, include=include)
    return mcp, svc, functions


def create_dsh_mcp(service: McpService | None = None) -> tuple[Any, McpService, dict]:
    return create_mcp(include=DSH_HTTP_TOOL_NAMES, service=service)
