from datetime import datetime, timezone
from threading import Lock
import json
import hashlib
import copy
from langchain_core.messages import HumanMessage
from graph import create_agent_app
from runtime_context import set_thread_id, log_event, get_request_id
from web_task_runtime import update_task_runtime_from_node
from app.api.schemas.chat import ChatRequest
from actions import execute_confirmed_action, append_audit_log


class AgentRunner:
    def __init__(self):
        self._app = create_agent_app()
        self._lock = Lock()
        self._session_store: dict[str, dict] = {}

    def _default_snapshot(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
            "last_answer": "",
            "last_reasoning": "",
            "updated_at": "",
            "action_pending_queue": [],
            "action_execution_logs": [],
            "pending_action_results": [],
        }

    def _now_iso_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _make_stream_event(self, seq: int, event_type: str, session_id: str, data: dict) -> dict:
        return {
            "schema": "mm-agent.stream.v1",
            "seq": seq,
            "ts": self._now_iso_utc(),
            "type": event_type,
            "session_id": session_id,
            "data": data,
        }

    def _parse_action_tool_payload(self, raw_tool_content: str) -> dict | None:
        try:
            payload = json.loads(raw_tool_content)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        source = str(payload.get("source", "")).strip()
        if not source.startswith("action_"):
            return None

        data_raw = payload.get("data", "")
        data_obj = {}
        if isinstance(data_raw, str):
            try:
                parsed = json.loads(data_raw)
                if isinstance(parsed, dict):
                    data_obj = parsed
            except Exception:
                data_obj = {}

        return {
            "source": source,
            "query": str(payload.get("query", "")).strip(),
            "ok": bool(payload.get("ok", False)),
            "error": str(payload.get("error", "")).strip(),
            "data": data_obj,
        }

    def _enqueue_pending_action(
        self,
        snapshot: dict,
        action_name: str,
        risk: str,
        query_text: str,
        message_text: str,
        confirm_payload: dict,
    ) -> dict:
        dedupe_key = (
            f"{action_name}|{query_text}|"
            f"{json.dumps(confirm_payload, ensure_ascii=False, sort_keys=True)}"
        )
        exists_row = next((x for x in snapshot["action_pending_queue"] if x.get("dedupe_key") == dedupe_key), None)
        if exists_row:
            return dict(exists_row)

        stable_id = hashlib.sha1(dedupe_key.encode("utf-8")).hexdigest()[:12]
        row = {
            "id": f"act_{stable_id}",
            "dedupe_key": dedupe_key,
            "action": action_name,
            "risk": risk,
            "status": "pending_confirmation",
            "message": message_text,
            "query": query_text,
            "confirm_payload": confirm_payload,
        }
        snapshot["action_pending_queue"].append(row)
        return dict(row)

    def _apply_action_updates_from_node_state(self, node_state: dict, snapshot: dict) -> dict:
        updates = {"new_pending": [], "new_logs": []}
        for msg in node_state.get("messages", []):
            if getattr(msg, "type", "") != "tool":
                continue
            action_payload = self._parse_action_tool_payload(getattr(msg, "content", ""))
            if not action_payload:
                continue
            action_data = action_payload.get("data", {})
            status = str(action_data.get("status", "")).strip()
            action_name = action_payload.get("source", "")
            risk = str(action_data.get("risk", "high")).strip() or "high"
            query_text = action_payload.get("query", "")
            message_text = str(action_data.get("message", "")).strip() or action_payload.get("error", "")
            confirm_payload = action_data.get("confirm_payload", {}) or {}

            if status == "pending_confirmation" and bool(action_data.get("requires_confirmation", False)):
                before_count = len(snapshot["action_pending_queue"])
                row = self._enqueue_pending_action(
                    snapshot=snapshot,
                    action_name=action_name,
                    risk=risk,
                    query_text=query_text,
                    message_text=message_text,
                    confirm_payload=confirm_payload,
                )
                if len(snapshot["action_pending_queue"]) > before_count:
                    updates["new_pending"].append(dict(row))
            elif status in {"executed", "failed"}:
                row = {
                    "action": action_name,
                    "status": status,
                    "message": message_text,
                    "output_path": str(action_data.get("output_path", "")),
                    "command_output": str(action_data.get("command_output", "")),
                }
                exists = any(
                    x.get("action") == row["action"]
                    and x.get("status") == row["status"]
                    and x.get("message") == row["message"]
                    and x.get("output_path") == row["output_path"]
                    for x in snapshot["action_execution_logs"]
                )
                if not exists:
                    snapshot["action_execution_logs"].append(row)
                    updates["new_logs"].append(dict(row))
        return updates

    def _build_input_payload(self, req: ChatRequest, snapshot: dict) -> dict:
        input_payload = {"messages": [HumanMessage(content=req.message)]}
        if req.inputs:
            raw_inputs = req.inputs.model_dump(exclude_none=True)
            input_payload.update(raw_inputs)
        elif snapshot.get("pending_action_results"):
            input_payload["action_results"] = snapshot.get("pending_action_results", [])
        snapshot["pending_action_results"] = []
        return input_payload

    def run_chat(self, session_id: str, req: ChatRequest) -> dict:
        set_thread_id(session_id)
        config = {"configurable": {"thread_id": session_id}}
        with self._lock:
            snapshot = copy.deepcopy(self._session_store.get(session_id, self._default_snapshot(session_id)))
        task_runtime = {"step_timeline": [], "last_failure_summary": ""}
        final_answer = ""
        reasoning_text = ""

        input_payload = self._build_input_payload(req, snapshot)

        log_event("fastapi_chat", "user_query", meta={"thread_id": session_id, "chars": len(req.message)})
        for output in self._app.stream(input_payload, config=config, stream_mode="updates"):
            for node_name, node_state in output.items():
                update_task_runtime_from_node(node_name, node_state, task_runtime)
                self._apply_action_updates_from_node_state(node_state, snapshot)
                if node_name == "synthesizer":
                    latest_msg = node_state["messages"][-1]
                    final_answer = latest_msg.content
                    reasoning_text = latest_msg.additional_kwargs.get("reasoning_content", "")

        snapshot.update(
            {
                "session_id": session_id,
                "task_runtime": task_runtime,
                "last_answer": final_answer,
                "last_reasoning": reasoning_text,
                "updated_at": datetime.now().isoformat(),
            }
        )
        with self._lock:
            self._session_store[session_id] = snapshot
        return snapshot

    def stream_chat(self, session_id: str, req: ChatRequest):
        set_thread_id(session_id)
        config = {"configurable": {"thread_id": session_id}}
        with self._lock:
            snapshot = copy.deepcopy(self._session_store.get(session_id, self._default_snapshot(session_id)))
        task_runtime = {"step_timeline": [], "last_failure_summary": ""}
        final_answer = ""
        reasoning_text = ""
        input_payload = self._build_input_payload(req, snapshot)
        seq = 1
        prev_answer_preview = ""

        log_event("fastapi_stream", "user_query", meta={"thread_id": session_id, "chars": len(req.message)})
        yield self._make_stream_event(
            seq,
            "run_started",
            session_id,
            {
                "message": req.message,
                "has_inputs": bool(req.inputs),
            },
        )
        seq += 1
        for output in self._app.stream(input_payload, config=config, stream_mode="updates"):
            for node_name, node_state in output.items():
                update_task_runtime_from_node(node_name, node_state, task_runtime)
                action_updates = self._apply_action_updates_from_node_state(node_state, snapshot)
                if node_name == "synthesizer":
                    latest_msg = node_state["messages"][-1]
                    final_answer = latest_msg.content
                    reasoning_text = latest_msg.additional_kwargs.get("reasoning_content", "")

                node_state_brief = {}
                for key in ("task_plan", "current_step", "step_status", "critic_score", "critic_feedback"):
                    if key in node_state:
                        node_state_brief[key] = node_state.get(key)
                timeline = task_runtime.get("step_timeline", [])
                step_tail = timeline[-1] if timeline else {}
                yield self._make_stream_event(
                    seq,
                    "node_update",
                    session_id,
                    {
                        "node": node_name,
                        "node_state": node_state_brief,
                        "step_tail": step_tail,
                        "answer_preview": final_answer[:200],
                    },
                )
                seq += 1

                if node_name == "planner" and node_state_brief.get("task_plan"):
                    yield self._make_stream_event(
                        seq,
                        "planner_update",
                        session_id,
                        {"task_plan": node_state_brief.get("task_plan", [])},
                    )
                    seq += 1

                if node_name == "critic":
                    yield self._make_stream_event(
                        seq,
                        "critic_update",
                        session_id,
                        {
                            "critic_score": node_state_brief.get("critic_score"),
                            "critic_feedback": node_state_brief.get("critic_feedback", ""),
                        },
                    )
                    seq += 1

                current_preview = final_answer[:200]
                if current_preview and current_preview != prev_answer_preview:
                    prev_answer_preview = current_preview
                    yield self._make_stream_event(
                        seq,
                        "synthesizer_update",
                        session_id,
                        {
                            "answer_preview": current_preview,
                            "reasoning_preview": reasoning_text[:200],
                        },
                    )
                    seq += 1

                for pending in action_updates.get("new_pending", []):
                    yield self._make_stream_event(
                        seq,
                        "action_required",
                        session_id,
                        {
                            "action_id": pending.get("id", ""),
                            "action": pending.get("action", ""),
                            "risk": pending.get("risk", "high"),
                            "message": pending.get("message", ""),
                        },
                    )
                    seq += 1

                for row in action_updates.get("new_logs", []):
                    yield self._make_stream_event(
                        seq,
                        "action_result",
                        session_id,
                        row,
                    )
                    seq += 1

        snapshot.update(
            {
                "session_id": session_id,
                "task_runtime": task_runtime,
                "last_answer": final_answer,
                "last_reasoning": reasoning_text,
                "updated_at": datetime.now().isoformat(),
            }
        )
        with self._lock:
            self._session_store[session_id] = snapshot
        yield self._make_stream_event(
            seq,
            "run_completed",
            session_id,
            {
                "task_runtime": task_runtime,
                "answer": final_answer,
                "reasoning": reasoning_text,
                "pending_action_count": len(snapshot.get("action_pending_queue", [])),
            },
        )

    def confirm_action(self, session_id: str, action_id: str, approve: bool) -> dict:
        with self._lock:
            snapshot = copy.deepcopy(self._session_store.get(session_id, self._default_snapshot(session_id)))
        queue = snapshot.get("action_pending_queue", [])
        target = next((x for x in queue if x.get("id") == action_id), None)
        if not target:
            return {"ok": False, "message": "action_id 不存在", "session_id": session_id}

        action = target.get("action", "")
        risk = target.get("risk", "high")
        query = target.get("query", "")
        if approve:
            result = execute_confirmed_action(action, target.get("confirm_payload", {}))
            status = "executed" if result.get("ok", False) else "failed"
            message = result.get("message", "")
            append_audit_log(action, risk, status, message, meta={"query": query, "confirmed_in_api": True})
            row = {
                "action": action,
                "status": status,
                "message": message,
                "output_path": result.get("output_path", ""),
                "command_output": result.get("command_output", ""),
            }
        else:
            append_audit_log(
                action,
                risk,
                "rejected",
                "用户在API端拒绝执行该动作。",
                meta={"query": query, "confirmed_in_api": False},
            )
            row = {
                "action": action,
                "status": "rejected",
                "message": "用户拒绝执行",
                "output_path": "",
                "command_output": "",
            }

        snapshot.setdefault("action_execution_logs", []).append(dict(row))
        snapshot.setdefault("pending_action_results", []).append(dict(row))
        snapshot["action_pending_queue"] = [x for x in queue if x.get("id") != action_id]
        snapshot["updated_at"] = datetime.now().isoformat()
        with self._lock:
            self._session_store[session_id] = snapshot
        return {"ok": True, "session_id": session_id, "action_id": action_id, "result": row}

    def request_action(
        self,
        session_id: str,
        action_name: str,
        risk: str,
        query: str,
        message: str,
        confirm_payload: dict,
    ) -> dict:
        with self._lock:
            snapshot = copy.deepcopy(self._session_store.get(session_id, self._default_snapshot(session_id)))

        before_count = len(snapshot.get("action_pending_queue", []))
        row = self._enqueue_pending_action(
            snapshot=snapshot,
            action_name=action_name,
            risk=(risk or "high").strip().lower() or "high",
            query_text=query or "",
            message_text=message or "该动作需要确认后执行。",
            confirm_payload=confirm_payload or {},
        )
        added = len(snapshot.get("action_pending_queue", [])) > before_count
        if added:
            append_audit_log(
                row.get("action", action_name),
                row.get("risk", risk),
                "pending_confirmation",
                row.get("message", message),
                meta={
                    "query": row.get("query", query),
                    "requested_in_mcp": True,
                    "request_id": get_request_id(),
                },
            )

        snapshot["updated_at"] = datetime.now().isoformat()
        with self._lock:
            self._session_store[session_id] = snapshot

        return {
            "ok": True,
            "session_id": session_id,
            "status": "queued" if added else "already_exists",
            "action_id": row.get("id", ""),
            "pending_action": row,
        }

    def get_state(self, session_id: str) -> dict:
        with self._lock:
            return self._session_store.get(
                session_id, self._default_snapshot(session_id)
            )
