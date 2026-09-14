"""
Multi-Modal AI Insights Agent MCP Server

Run:
    python mcp_server.py

This server exposes core agent capabilities as MCP tools:
    - healthz
    - research_search
    - chat
    - stream_chat
    - get_state
    - action_request_*
    - confirm_action
    - reject_action
    - session_*/actions_*/system_* (grouped aliases)
"""

from typing import Any

from app.service.agent_runner import AgentRunner
from mcp_tools.service import McpService

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "缺少 mcp 依赖，请先安装：pip install mcp\n"
        f"原始错误: {e}"
    )


mcp = FastMCP("multi-modal-ai-insights-agent")
service = McpService(runner=AgentRunner())


@mcp.tool()
def healthz() -> dict[str, Any]:
    """检查 MCP 服务可用性。"""
    return service.healthz()


@mcp.tool()
def chat(session_id: str, message: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    发起一轮聊天并返回最终回答。

    Args:
        session_id: 会话 ID（可自定义，用于隔离上下文）
        message: 用户输入
        inputs: 可选附加上下文（vision/action_results/user_profile 等）
    """
    return service.chat(session_id=session_id, message=message, inputs=inputs)


@mcp.tool()
def research_search(query: str, source: str = "auto") -> dict[str, Any]:
    """
    MCP 统一检索入口。

    Args:
        query: 检索关键词
        source: dify / web / auto
    """
    return service.research_search(query=query, source=source)


@mcp.tool()
def stream_chat(
    session_id: str,
    message: str,
    inputs: dict[str, Any] | None = None,
    max_events: int = 200,
) -> dict[str, Any]:
    """
    以“事件列表”形式返回流式执行结果（便于不支持原生流的 MCP 客户端）。

    Args:
        session_id: 会话 ID
        message: 用户输入
        inputs: 可选附加上下文
        max_events: 最多返回多少条事件，防止超大响应
    """
    return service.stream_chat(session_id=session_id, message=message, inputs=inputs, max_events=max_events)


@mcp.tool()
def get_state(session_id: str) -> dict[str, Any]:
    """获取会话状态快照。"""
    return service.get_state(session_id=session_id)


@mcp.tool()
def action_request_write_file(session_id: str, filename: str, content: str) -> dict[str, Any]:
    """创建“写文件”待确认动作（MCP 侧审批闭环入口）。"""
    return service.action_request_write_file(session_id=session_id, filename=filename, content=content)


@mcp.tool()
def action_request_email_draft(session_id: str, recipient: str, subject: str, body: str) -> dict[str, Any]:
    """创建“邮件草稿”待确认动作（MCP 侧审批闭环入口）。"""
    return service.action_request_email_draft(
        session_id=session_id, recipient=recipient, subject=subject, body=body
    )


@mcp.tool()
def action_request_shell_command(session_id: str, command: str) -> dict[str, Any]:
    """创建“命令执行”待确认动作（高风险，默认审批后执行）。"""
    return service.action_request_shell_command(session_id=session_id, command=command)


@mcp.tool()
def confirm_action(session_id: str, action_id: str) -> dict[str, Any]:
    """确认执行待确认动作。"""
    return service.confirm_action(session_id=session_id, action_id=action_id)


@mcp.tool()
def reject_action(session_id: str, action_id: str) -> dict[str, Any]:
    """拒绝执行待确认动作。"""
    return service.reject_action(session_id=session_id, action_id=action_id)


# -------- Grouped aliases (recommended for client-side organization) --------

@mcp.tool()
def system_healthz() -> dict[str, Any]:
    """分组别名：system.healthz"""
    return healthz()


@mcp.tool()
def research_lookup(query: str, source: str = "auto") -> dict[str, Any]:
    """分组别名：research.search"""
    return research_search(query=query, source=source)


@mcp.tool()
def session_chat(session_id: str, message: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """分组别名：session.chat"""
    return chat(session_id=session_id, message=message, inputs=inputs)


@mcp.tool()
def session_stream_chat(
    session_id: str,
    message: str,
    inputs: dict[str, Any] | None = None,
    max_events: int = 200,
) -> dict[str, Any]:
    """分组别名：session.stream_chat"""
    return stream_chat(session_id=session_id, message=message, inputs=inputs, max_events=max_events)


@mcp.tool()
def session_get_state(session_id: str) -> dict[str, Any]:
    """分组别名：session.get_state"""
    return get_state(session_id=session_id)


@mcp.tool()
def actions_confirm(session_id: str, action_id: str) -> dict[str, Any]:
    """分组别名：actions.confirm"""
    return confirm_action(session_id=session_id, action_id=action_id)


@mcp.tool()
def actions_request_write_file(session_id: str, filename: str, content: str) -> dict[str, Any]:
    """分组别名：actions.request_write_file"""
    return action_request_write_file(session_id=session_id, filename=filename, content=content)


@mcp.tool()
def actions_request_email_draft(session_id: str, recipient: str, subject: str, body: str) -> dict[str, Any]:
    """分组别名：actions.request_email_draft"""
    return action_request_email_draft(
        session_id=session_id,
        recipient=recipient,
        subject=subject,
        body=body,
    )


@mcp.tool()
def actions_request_shell_command(session_id: str, command: str) -> dict[str, Any]:
    """分组别名：actions.request_shell_command"""
    return action_request_shell_command(session_id=session_id, command=command)


@mcp.tool()
def actions_reject(session_id: str, action_id: str) -> dict[str, Any]:
    """分组别名：actions.reject"""
    return reject_action(session_id=session_id, action_id=action_id)


if __name__ == "__main__":
    mcp.run()
