"""
Multi-Modal AI Insights Agent MCP Server

Run:
    python mcp_server.py

stdio 全量工具（含 chat 别名）给 Cursor / harness。
dsh 走 FastAPI `/v1/mcp`，只注册 DSH_HTTP_TOOL_NAMES。
"""

from mcp_tools.factory import create_mcp

mcp, service, _TOOLS = create_mcp(include=None)

healthz = _TOOLS["healthz"]
chat = _TOOLS["chat"]
research_search = _TOOLS["research_search"]
stream_chat = _TOOLS["stream_chat"]
get_state = _TOOLS["get_state"]
action_request_write_file = _TOOLS["action_request_write_file"]
action_request_email_draft = _TOOLS["action_request_email_draft"]
action_request_shell_command = _TOOLS["action_request_shell_command"]
confirm_action = _TOOLS["confirm_action"]
reject_action = _TOOLS["reject_action"]
paper_run_start = _TOOLS["paper_run_start"]
paper_run_status = _TOOLS["paper_run_status"]
system_healthz = _TOOLS["system_healthz"]
research_lookup = _TOOLS["research_lookup"]
session_chat = _TOOLS["session_chat"]
session_stream_chat = _TOOLS["session_stream_chat"]
session_get_state = _TOOLS["session_get_state"]
actions_confirm = _TOOLS["actions_confirm"]
actions_request_write_file = _TOOLS["actions_request_write_file"]
actions_request_email_draft = _TOOLS["actions_request_email_draft"]
actions_request_shell_command = _TOOLS["actions_request_shell_command"]
actions_reject = _TOOLS["actions_reject"]


if __name__ == "__main__":
    mcp.run()
