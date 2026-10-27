import time
from typing import Any

import mcp_server

from .base import HarnessRunner


class McpRunner(HarnessRunner):
    def run_case(self, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action = case.get("action", "")
        session_id = str(case.get("session_id", "demo"))
        t0 = time.perf_counter()

        try:
            if action == "healthz":
                payload = mcp_server.healthz()
            elif action == "research_search":
                payload = mcp_server.research_search(
                    query=str(case.get("query", "")),
                    source=str(case.get("source", "auto")),
                )
            elif action == "chat":
                payload = mcp_server.chat(
                    session_id=session_id,
                    message=str(case.get("message", "")),
                )
            elif action == "stream_chat":
                payload = mcp_server.stream_chat(
                    session_id=session_id,
                    message=str(case.get("message", "")),
                    max_events=int(case.get("max_events", 50)),
                )
            elif action == "state":
                payload = mcp_server.get_state(session_id=session_id)
            elif action == "confirm_action":
                action_id = str(case.get("action_id") or context.get("last_action_id", ""))
                payload = mcp_server.confirm_action(session_id=session_id, action_id=action_id)
            elif action == "reject_action":
                action_id = str(case.get("action_id") or context.get("last_action_id", ""))
                payload = mcp_server.reject_action(session_id=session_id, action_id=action_id)
            else:
                payload = {"ok": False, "error": f"unsupported mcp action: {action}"}
        except Exception as e:
            payload = {"ok": False, "error": str(e)}

        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": bool(payload.get("ok", False)),
            "status_code": 200 if bool(payload.get("ok", False)) else 500,
            "latency_ms": latency_ms,
            "payload": payload,
        }
