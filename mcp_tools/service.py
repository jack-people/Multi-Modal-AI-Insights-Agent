from __future__ import annotations

import json
from typing import Any

from app.api.deps import get_agent_runner
from app.api.schemas.chat import ChatInputs, ChatRequest
from app.service.agent_runner import AgentRunner
from mcp_tools import paper_jobs
from mcp_tools.context import attach_request_meta, resolve_session_id
from tools import search_dify_arxiv_db, search_web_news


class McpService:
    """MCP 工具的实现。公开方法即工具：签名与 docstring 直接用于 MCP schema。"""

    def __init__(self, runner: AgentRunner | None = None):
        self._runner = runner

    @property
    def runner(self) -> AgentRunner:
        return self._runner or get_agent_runner()

    @staticmethod
    def _out(payload: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
        return attach_request_meta(payload, session_id=session_id)

    @staticmethod
    def _build_chat_request(message: str, inputs: dict[str, Any] | None = None) -> ChatRequest:
        if inputs:
            return ChatRequest(message=message, inputs=ChatInputs(**inputs))
        return ChatRequest(message=message)

    @staticmethod
    def _invoke_search_tool(tool_obj: Any, query: str) -> dict[str, Any]:
        raw = tool_obj.invoke({"query": query}) if hasattr(tool_obj, "invoke") else tool_obj(query)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return {"ok": True, **json.loads(raw)}
            except Exception:
                return {"ok": False, "error": "tool 返回非 JSON 字符串", "raw": raw}
        return {"ok": False, "error": f"tool 返回未知类型: {type(raw).__name__}"}

    # ---- tools ----

    def healthz(self) -> dict[str, Any]:
        """检查 MCP 服务可用性。"""
        return self._out({"ok": True, "service": "multi-modal-ai-insights-agent-mcp"})

    def chat(
        self,
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发起一轮聊天并返回最终回答。不要暴露给 dsh。"""
        sid = resolve_session_id(session_id)
        snapshot = self.runner.run_chat(session_id=sid, req=self._build_chat_request(message, inputs))
        return self._out(
            {
                "ok": True,
                "session_id": sid,
                "answer": snapshot.get("last_answer", ""),
                "reasoning": snapshot.get("last_reasoning", ""),
                "task_runtime": snapshot.get("task_runtime", {}),
            },
            session_id=sid,
        )

    def stream_chat(
        self,
        session_id: str | None = None,
        message: str = "",
        inputs: dict[str, Any] | None = None,
        max_events: int = 200,
    ) -> dict[str, Any]:
        """以事件列表形式返回流式执行结果。不要暴露给 dsh。"""
        sid = resolve_session_id(session_id)
        limit = max(1, int(max_events))
        events: list[dict[str, Any]] = []
        for item in self.runner.stream_chat(session_id=sid, req=self._build_chat_request(message, inputs)):
            events.append(item)
            if len(events) >= limit:
                break
        completed = bool(events and events[-1].get("type") == "run_completed")
        return self._out(
            {
                "ok": True,
                "session_id": sid,
                "event_count": len(events),
                "truncated": not completed,
                "events": events,
            },
            session_id=sid,
        )

    def research_search(self, query: str, source: str = "auto") -> dict[str, Any]:
        """MCP 统一检索入口。source: dify / web / auto。"""
        mode = (source or "auto").strip().lower()
        if mode not in {"dify", "web", "auto"}:
            return self._out(
                {
                    "ok": False,
                    "error_code": "MM400_BAD_SOURCE",
                    "message": "source 仅支持 dify/web/auto",
                    "detail": {"source": source},
                }
            )

        if mode != "web":
            result = self._invoke_search_tool(search_dify_arxiv_db, query)
            if mode == "dify" or result.get("ok", False):
                result["requested_source"] = mode
                if mode == "auto":
                    result["selected_source"] = str(result.get("source", "dify_arxiv_db"))
                return self._out(result)

        result = self._invoke_search_tool(search_web_news, query)
        result["requested_source"] = mode
        if mode == "auto":
            result["selected_source"] = str(result.get("source", "web_news"))
            result["fallback_from"] = "dify_arxiv_db"
        return self._out(result)

    def get_state(self, session_id: str | None = None) -> dict[str, Any]:
        """获取会话状态快照。session_id 可省略，由服务端缺省。"""
        sid = resolve_session_id(session_id)
        snapshot = self.runner.get_state(session_id=sid)
        return self._out(
            {
                "ok": True,
                "session_id": sid,
                "task_runtime": snapshot.get("task_runtime", {}),
                "last_answer": snapshot.get("last_answer", ""),
                "last_reasoning": snapshot.get("last_reasoning", ""),
                "updated_at": snapshot.get("updated_at", ""),
                "action_pending_queue": snapshot.get("action_pending_queue", []),
                "action_execution_logs": snapshot.get("action_execution_logs", []),
            },
            session_id=sid,
        )

    def _request_action(
        self,
        session_id: str | None,
        action_name: str,
        risk: str,
        query: str,
        message: str,
        confirm_payload: dict[str, Any],
    ) -> dict[str, Any]:
        sid = resolve_session_id(session_id)
        result = self.runner.request_action(
            session_id=sid,
            action_name=action_name,
            risk=risk,
            query=query,
            message=message,
            confirm_payload=confirm_payload,
        )
        return self._out(result, session_id=sid)

    def action_request_write_file(
        self,
        session_id: str | None = None,
        filename: str = "",
        content: str = "",
    ) -> dict[str, Any]:
        """创建写文件待确认动作。"""
        return self._request_action(
            session_id,
            action_name="action_write_report_file",
            risk="low",
            query=f"filename={filename}",
            message="MCP 请求写文件动作，等待确认执行。",
            confirm_payload={"filename": filename, "content": content},
        )

    def action_request_email_draft(
        self,
        session_id: str | None = None,
        recipient: str = "",
        subject: str = "",
        body: str = "",
    ) -> dict[str, Any]:
        """创建邮件草稿待确认动作。"""
        return self._request_action(
            session_id,
            action_name="action_create_email_draft",
            risk="medium",
            query=f"recipient={recipient};subject={subject}",
            message="MCP 请求创建邮件草稿，等待确认执行。",
            confirm_payload={"recipient": recipient, "subject": subject, "body": body},
        )

    def action_request_shell_command(
        self,
        session_id: str | None = None,
        command: str = "",
    ) -> dict[str, Any]:
        """创建命令执行待确认动作（高风险）。"""
        return self._request_action(
            session_id,
            action_name="action_run_shell_command",
            risk="high",
            query=command,
            message="MCP 请求执行命令，属于高风险动作，等待确认。",
            confirm_payload={"command": command},
        )

    def _decide_action(self, session_id: str | None, action_id: str, approve: bool) -> dict[str, Any]:
        sid = resolve_session_id(session_id)
        result = self.runner.confirm_action(session_id=sid, action_id=action_id, approve=approve)
        if not result.get("ok", False):
            result = {
                "ok": False,
                "error_code": "MM404_ACTION_NOT_FOUND",
                "message": result.get("message", "action_id 不存在"),
                "detail": {"session_id": sid, "action_id": action_id},
            }
        return self._out(result, session_id=sid)

    def confirm_action(self, session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """确认执行待确认动作。"""
        return self._decide_action(session_id, action_id, approve=True)

    def reject_action(self, session_id: str | None = None, action_id: str = "") -> dict[str, Any]:
        """拒绝执行待确认动作。"""
        return self._decide_action(session_id, action_id, approve=False)

    def paper_run_start(self, paper_limit: int = 10, top_k: int = 10, news_limit: int = 0) -> dict[str, Any]:
        """启动论文分析任务，立即返回 job_id。"""
        return self._out(paper_jobs.paper_run_start(paper_limit=paper_limit, top_k=top_k, news_limit=news_limit))

    def paper_run_status(self, job_id: str) -> dict[str, Any]:
        """查询论文分析任务状态与报告路径。"""
        return self._out(paper_jobs.paper_run_status(job_id=job_id))
