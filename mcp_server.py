"""
Multi-Modal AI Insights Agent MCP Server

Run:
    python mcp_server.py

stdio 全量工具（含 chat 与分组别名）给 Cursor / harness。
dsh 走 FastAPI `/v1/mcp`，只注册 DSH_HTTP_TOOL_NAMES（见 app/api/main.py）。
"""

from mcp_tools.factory import create_mcp

mcp, TOOLS = create_mcp()

# harness/runners/mcp_runner.py 按模块属性调用工具函数
globals().update(TOOLS)


if __name__ == "__main__":
    mcp.run()
