"""将 dsh 用的 FastMCP 挂到 FastAPI。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp_tools.factory import create_dsh_mcp


def _asgi_app(mcp: Any) -> Any:
    mcp.streamable_http_app()
    try:
        from mcp.server.fastmcp.server import StreamableHTTPASGIApp

        return StreamableHTTPASGIApp(mcp.session_manager)
    except Exception:
        return mcp.streamable_http_app()


def attach_dsh_mcp(app: Any) -> Any:
    mcp, _, _ = create_dsh_mcp()
    app.mount("/v1/mcp", _asgi_app(mcp))
    app.state.dsh_mcp = mcp
    return mcp


def mcp_lifespan(mcp: Any):
    @asynccontextmanager
    async def _lifespan(_app: Any) -> AsyncIterator[None]:
        if mcp is None:
            yield
            return
        mcp.streamable_http_app()
        async with mcp.session_manager.run():
            yield

    return _lifespan
