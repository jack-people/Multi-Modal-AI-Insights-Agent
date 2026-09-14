import time
from typing import Any

from app.api.schemas.chat import ChatRequest
from app.service.agent_runner import AgentRunner

from .base import HarnessRunner


class LocalRunner(HarnessRunner):
    def __init__(self):
        self.runner = AgentRunner()

    def run_case(self, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action = case.get("action", "")
        session_id = str(case.get("session_id", "demo"))
        t0 = time.perf_counter()

        try:
            if action == "healthz":
                payload = {"ok": True, "service": "local-runner"}
            elif action == "chat":
                req = ChatRequest(message=str(case.get("message", "")))
                snapshot = self.runner.run_chat(session_id=session_id, req=req)
                payload = {
                    "ok": True,
                    "session_id": session_id,
                    "answer": snapshot.get("last_answer", ""),
                    "reasoning": snapshot.get("last_reasoning", ""),
                    "task_runtime": snapshot.get("task_runtime", {}),
                }
            elif action == "state":
                snapshot = self.runner.get_state(session_id=session_id)
                payload = {
                    "ok": True,
                    "session_id": session_id,
                    "task_runtime": snapshot.get("task_runtime", {}),
                    "last_answer": snapshot.get("last_answer", ""),
                    "last_reasoning": snapshot.get("last_reasoning", ""),
                    "updated_at": snapshot.get("updated_at", ""),
                    "action_pending_queue": snapshot.get("action_pending_queue", []),
                    "action_execution_logs": snapshot.get("action_execution_logs", []),
                }
            elif action == "stream_chat":
                req = ChatRequest(message=str(case.get("message", "")))
                events = list(self.runner.stream_chat(session_id=session_id, req=req))
                payload = {"ok": True, "event_count": len(events), "events": events}
            elif action == "request_shell_action":
                payload = self.runner.request_action(
                    session_id=session_id,
                    action_name="action_run_shell_command",
                    risk="high",
                    query=str(case.get("command", "")),
                    message="Harness 请求高风险命令动作，等待确认。",
                    confirm_payload={"command": str(case.get("command", ""))},
                )
            elif action == "confirm_action":
                action_id = str(case.get("action_id") or context.get("last_action_id", ""))
                payload = self.runner.confirm_action(session_id=session_id, action_id=action_id, approve=True)
            elif action == "reject_action":
                action_id = str(case.get("action_id") or context.get("last_action_id", ""))
                payload = self.runner.confirm_action(session_id=session_id, action_id=action_id, approve=False)
            else:
                payload = {"ok": False, "error": f"unsupported local action: {action}"}
        except Exception as e:
            payload = {"ok": False, "error": str(e)}

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": bool(payload.get("ok", False)),
            "status_code": 200 if bool(payload.get("ok", False)) else 500,
            "latency_ms": latency_ms,
            "payload": payload,
        }
