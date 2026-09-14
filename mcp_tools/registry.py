from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any

from mcp_tools.context import attach_request_meta
from mcp_tools.paper_jobs import paper_run_start as start_paper_job
from mcp_tools.paper_jobs import paper_run_status as status_paper_job
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

PAPER_TOOL_NAMES: tuple[str, ...] = (
    "paper_run_start",
    "paper_run_status",
)

DSH_HTTP_TOOL_NAMES: tuple[str, ...] = DSH_TOOL_NAMES + PAPER_TOOL_NAMES

ALIAS_TOOL_NAMES: tuple[str, ...] = (
    "system_healthz",
    "research_lookup",
    "session_chat",
    "session_stream_chat",
    "session_get_state",
    "actions_confirm",
    "actions_request_write_file",
    "actions_request_email_draft",
    "actions_request_shell_command",
    "actions_reject",
)

CORE_CHAT_TOOL_NAMES: tuple[str, ...] = (
    "chat",
    "stream_chat",
)

FULL_TOOL_NAMES: tuple[str, ...] = DSH_TOOL_NAMES + CORE_CHAT_TOOL_NAMES + PAPER_TOOL_NAMES + ALIAS_TOOL_NAMES


def _mcp_guard(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        with action_confirm_required():
            result = fn(*args, **kwargs)
        if isinstance(result, dict):
            return attach_request_meta(result, session_id=result.get("session_id"))
        return result

    return wrapped


def build_tool_functions(service: McpService) -> dict[str, Callable[..., Any]]:
    @_mcp_guard
    def healthz() -> dict[str, Any]:
        """检查 MCP 服务可用性。"""
        return service.healthz()

    @_mcp_guard
    def chat(
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发起一轮聊天并返回最终回答。不要暴露给 dsh。"""
        return service.chat(session_id=session_id, message=message, inputs=inputs)

    @_mcp_guard
    def research_search(query: str, source: str = "auto") -> dict[str, Any]:
        """MCP 统一检索入口。source: dify / web / auto。"""
        return service.research_search(query=query, source=source)

    @_mcp_guard
    def stream_chat(
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
        max_events: int = 200,
    ) -> dict[str, Any]:
        """以事件列表形式返回流式执行结果。不要暴露给 dsh。"""
        return service.stream_chat(
            session_id=session_id,
            message=message,
            inputs=inputs,
            max_events=max_events,
        )

    @_mcp_guard
    def get_state(session_id: str | None = None) -> dict[str, Any]:
        """获取会话状态快照。session_id 可省略，由服务端缺省。"""
        return service.get_state(session_id=session_id)

    @_mcp_guard
    def action_request_write_file(
        session_id: str | None = None,
        filename: str = "",
        content: str = "",
    ) -> dict[str, Any]:
        """创建写文件待确认动作。"""
        return service.action_request_write_file(session_id=session_id, filename=filename, content=content)

    @_mcp_guard
    def action_request_email_draft(
        session_id: str | None = None,
        recipient: str = "",
        subject: str = "",
        body: str = "",
    ) -> dict[str, Any]:
        """创建邮件草稿待确认动作。"""
        return service.action_request_email_draft(
            session_id=session_id,
            recipient=recipient,
            subject=subject,
            body=body,
        )

    @_mcp_guard
    def action_request_shell_command(
        session_id: str | None = None,
        command: str = "",
    ) -> dict[str, Any]:
        """创建命令执行待确认动作（高风险）。"""
        return service.action_request_shell_command(session_id=session_id, command=command)

    @_mcp_guard
    def confirm_action(session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """确认执行待确认动作。"""
        return service.confirm_action(session_id=session_id, action_id=action_id)

    @_mcp_guard
    def reject_action(session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """拒绝执行待确认动作。"""
        return service.reject_action(session_id=session_id, action_id=action_id)

    @_mcp_guard
    def paper_run_start(paper_limit: int = 10, top_k: int = 10, news_limit: int = 0) -> dict[str, Any]:
        """启动论文分析任务，立即返回 job_id。"""
        return start_paper_job(paper_limit=paper_limit, top_k=top_k, news_limit=news_limit)

    @_mcp_guard
    def paper_run_status(job_id: str) -> dict[str, Any]:
        """查询论文分析任务状态与报告路径。"""
        return status_paper_job(job_id=job_id)

    @_mcp_guard
    def system_healthz() -> dict[str, Any]:
        """分组别名：system.healthz"""
        return healthz()

    @_mcp_guard
    def research_lookup(query: str, source: str = "auto") -> dict[str, Any]:
        """分组别名：research.search"""
        return research_search(query=query, source=source)

    @_mcp_guard
    def session_chat(
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """分组别名：session.chat"""
        return chat(session_id=session_id, message=message, inputs=inputs)

    @_mcp_guard
    def session_stream_chat(
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
        max_events: int = 200,
    ) -> dict[str, Any]:
        """分组别名：session.stream_chat"""
        return stream_chat(session_id=session_id, message=message, inputs=inputs, max_events=max_events)

    @_mcp_guard
    def session_get_state(session_id: str | None = None) -> dict[str, Any]:
        """分组别名：session.get_state"""
        return get_state(session_id=session_id)

    @_mcp_guard
    def actions_confirm(session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """分组别名：actions.confirm"""
        return confirm_action(session_id=session_id, action_id=action_id)

    @_mcp_guard
    def actions_request_write_file(
        session_id: str | None = None,
        filename: str = "",
        content: str = "",
    ) -> dict[str, Any]:
        """分组别名：actions.request_write_file"""
        return action_request_write_file(session_id=session_id, filename=filename, content=content)

    @_mcp_guard
    def actions_request_email_draft(
        session_id: str | None = None,
        recipient: str = "",
        subject: str = "",
        body: str = "",
    ) -> dict[str, Any]:
        """分组别名：actions.request_email_draft"""
        return action_request_email_draft(
            session_id=session_id,
            recipient=recipient,
            subject=subject,
            body=body,
        )

    @_mcp_guard
    def actions_request_shell_command(
        session_id: str | None = None,
        command: str = "",
    ) -> dict[str, Any]:
        """分组别名：actions.request_shell_command"""
        return action_request_shell_command(session_id=session_id, command=command)

    @_mcp_guard
    def actions_reject(session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """分组别名：actions.reject"""
        return reject_action(session_id=session_id, action_id=action_id)

    return {
        "healthz": healthz,
        "chat": chat,
        "research_search": research_search,
        "stream_chat": stream_chat,
        "get_state": get_state,
        "action_request_write_file": action_request_write_file,
        "action_request_email_draft": action_request_email_draft,
        "action_request_shell_command": action_request_shell_command,
        "confirm_action": confirm_action,
        "reject_action": reject_action,
        "paper_run_start": paper_run_start,
        "paper_run_status": paper_run_status,
        "system_healthz": system_healthz,
        "research_lookup": research_lookup,
        "session_chat": session_chat,
        "session_stream_chat": session_stream_chat,
        "session_get_state": session_get_state,
        "actions_confirm": actions_confirm,
        "actions_request_write_file": actions_request_write_file,
        "actions_request_email_draft": actions_request_email_draft,
        "actions_request_shell_command": actions_request_shell_command,
        "actions_reject": actions_reject,
    }


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
