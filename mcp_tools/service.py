import json
from typing import Any

from app.api.schemas.chat import ChatInputs, ChatRequest
from app.service.agent_runner import AgentRunner
from tools import search_dify_arxiv_db, search_web_news


class McpService:
    def __init__(self, runner: AgentRunner):
        self.runner = runner

    @staticmethod
    def _build_chat_request(message: str, inputs: dict[str, Any] | None = None) -> ChatRequest:
        if inputs:
            return ChatRequest(message=message, inputs=ChatInputs(**inputs))
        return ChatRequest(message=message)

    @staticmethod
    def _invoke_search_tool(tool_obj: Any, query: str) -> dict[str, Any]:
        if hasattr(tool_obj, "invoke"):
            raw = tool_obj.invoke({"query": query})
        else:
            raw = tool_obj(query)

        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return {"ok": True, **json.loads(raw)}
            except Exception:
                return {"ok": False, "error": "tool 返回非 JSON 字符串", "raw": raw}
        return {"ok": False, "error": f"tool 返回未知类型: {type(raw).__name__}"}

    def healthz(self) -> dict[str, Any]:
        return {"ok": True, "service": "multi-modal-ai-insights-agent-mcp"}

    def chat(self, session_id: str, message: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        req = self._build_chat_request(message=message, inputs=inputs)
        snapshot = self.runner.run_chat(session_id=session_id, req=req)
        return {
            "ok": True,
            "session_id": session_id,
            "answer": snapshot.get("last_answer", ""),
            "reasoning": snapshot.get("last_reasoning", ""),
            "task_runtime": snapshot.get("task_runtime", {}),
        }

    def research_search(self, query: str, source: str = "auto") -> dict[str, Any]:
        mode = (source or "auto").strip().lower()
        if mode not in {"dify", "web", "auto"}:
            return {
                "ok": False,
                "error_code": "MM400_BAD_SOURCE",
                "message": "source 仅支持 dify/web/auto",
                "detail": {"source": source},
            }

        if mode == "dify":
            result = self._invoke_search_tool(search_dify_arxiv_db, query)
            result["requested_source"] = "dify"
            return result

        if mode == "web":
            result = self._invoke_search_tool(search_web_news, query)
            result["requested_source"] = "web"
            return result

        dify_result = self._invoke_search_tool(search_dify_arxiv_db, query)
        if bool(dify_result.get("ok", False)):
            dify_result["requested_source"] = "auto"
            dify_result["selected_source"] = str(dify_result.get("source", "dify_arxiv_db"))
            return dify_result

        web_result = self._invoke_search_tool(search_web_news, query)
        web_result["requested_source"] = "auto"
        web_result["selected_source"] = str(web_result.get("source", "web_news"))
        web_result["fallback_from"] = "dify_arxiv_db"
        return web_result

    def stream_chat(
        self,
        session_id: str,
        message: str,
        inputs: dict[str, Any] | None = None,
        max_events: int = 200,
    ) -> dict[str, Any]:
        req = self._build_chat_request(message=message, inputs=inputs)
        events = []
        limit = max(1, int(max_events))
        for item in self.runner.stream_chat(session_id=session_id, req=req):
            events.append(item)
            if len(events) >= limit:
                break

        completed = bool(events and events[-1].get("type") == "run_completed")
        return {
            "ok": True,
            "session_id": session_id,
            "event_count": len(events),
            "truncated": not completed,
            "events": events,
        }

    def get_state(self, session_id: str) -> dict[str, Any]:
        snapshot = self.runner.get_state(session_id=session_id)
        return {
            "ok": True,
            "session_id": session_id,
            "task_runtime": snapshot.get("task_runtime", {}),
            "last_answer": snapshot.get("last_answer", ""),
            "last_reasoning": snapshot.get("last_reasoning", ""),
            "updated_at": snapshot.get("updated_at", ""),
            "action_pending_queue": snapshot.get("action_pending_queue", []),
            "action_execution_logs": snapshot.get("action_execution_logs", []),
        }

    def _request_action(
        self,
        session_id: str,
        action_name: str,
        risk: str,
        query: str,
        message: str,
        confirm_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.runner.request_action(
            session_id=session_id,
            action_name=action_name,
            risk=risk,
            query=query,
            message=message,
            confirm_payload=confirm_payload,
        )

    def action_request_write_file(self, session_id: str, filename: str, content: str) -> dict[str, Any]:
        return self._request_action(
            session_id=session_id,
            action_name="action_write_report_file",
            risk="low",
            query=f"filename={filename}",
            message="MCP 请求写文件动作，等待确认执行。",
            confirm_payload={"filename": filename, "content": content},
        )

    def action_request_email_draft(self, session_id: str, recipient: str, subject: str, body: str) -> dict[str, Any]:
        return self._request_action(
            session_id=session_id,
            action_name="action_create_email_draft",
            risk="medium",
            query=f"recipient={recipient};subject={subject}",
            message="MCP 请求创建邮件草稿，等待确认执行。",
            confirm_payload={"recipient": recipient, "subject": subject, "body": body},
        )

    def action_request_shell_command(self, session_id: str, command: str) -> dict[str, Any]:
        return self._request_action(
            session_id=session_id,
            action_name="action_run_shell_command",
            risk="high",
            query=command,
            message="MCP 请求执行命令，属于高风险动作，等待确认。",
            confirm_payload={"command": command},
        )

    @staticmethod
    def _decision_result(result: dict[str, Any], session_id: str, action_id: str) -> dict[str, Any]:
        if result.get("ok", False):
            return result
        return {
            "ok": False,
            "error_code": "MM404_ACTION_NOT_FOUND",
            "message": result.get("message", "action_id 不存在"),
            "detail": {"session_id": session_id, "action_id": action_id},
        }

    def confirm_action(self, session_id: str, action_id: str) -> dict[str, Any]:
        result = self.runner.confirm_action(session_id=session_id, action_id=action_id, approve=True)
        return self._decision_result(result=result, session_id=session_id, action_id=action_id)

    def reject_action(self, session_id: str, action_id: str) -> dict[str, Any]:
        result = self.runner.confirm_action(session_id=session_id, action_id=action_id, approve=False)
        return self._decision_result(result=result, session_id=session_id, action_id=action_id)
