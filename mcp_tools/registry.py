from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any

from mcp_tools.service import McpService
from runtime_context import action_confirm_required

DSH_TOOL_NAMES: tuple[str, ...] = (
    "healthz",
    "research_search",
    "get_state",
    "action_request_write_file",
    "action_request_email_draft",
    "action_request_shell_command",
    "confirm_action",
    "reject_action",
)

PAPER_TOOL_NAMES: tuple[str, ...] = ("paper_run_start", "paper_run_status")

CORE_CHAT_TOOL_NAMES: tuple[str, ...] = ("chat", "stream_chat")

# 分组别名（仅 stdio 全量表面保留，dsh 不注册）：别名 -> 真实工具
ALIASES: dict[str, str] = {
    "system_healthz": "healthz",
    "research_lookup": "research_search",
    "session_chat": "chat",
    "session_stream_chat": "stream_chat",
    "session_get_state": "get_state",
    "actions_confirm": "confirm_action",
    "actions_request_write_file": "action_request_write_file",
    "actions_request_email_draft": "action_request_email_draft",
    "actions_request_shell_command": "action_request_shell_command",
    "actions_reject": "reject_action",
}

DSH_HTTP_TOOL_NAMES: tuple[str, ...] = DSH_TOOL_NAMES + PAPER_TOOL_NAMES
FULL_TOOL_NAMES: tuple[str, ...] = DSH_TOOL_NAMES + CORE_CHAT_TOOL_NAMES + PAPER_TOOL_NAMES + tuple(ALIASES)


def _mcp_guard(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """MCP 入口一律禁止 action_* 自动执行，统一走待确认队列。"""

    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        with action_confirm_required():
            return fn(*args, **kwargs)

    return wrapped


def build_tool_functions(service: McpService) -> dict[str, Callable[..., Any]]:
    functions = {name: _mcp_guard(getattr(service, name)) for name in DSH_TOOL_NAMES + CORE_CHAT_TOOL_NAMES + PAPER_TOOL_NAMES}
    functions.update({alias: functions[target] for alias, target in ALIASES.items()})
    return functions


def register_tools(
    mcp: Any,
    service: McpService,
    include: Sequence[str] | None = None,
) -> dict[str, Callable[..., Any]]:
    functions = build_tool_functions(service)
    selected = list(FULL_TOOL_NAMES if include is None else include)
    unknown = [name for name in selected if name not in functions]
    if unknown:
        raise ValueError(f"未知 MCP 工具: {unknown}")
    for name in selected:
        mcp.tool(name=name)(functions[name])
    return functions
