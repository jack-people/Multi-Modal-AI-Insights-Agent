import re
from typing import Any


def _get_nested(payload: dict[str, Any], key: str) -> Any:
    cur: Any = payload
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate_case(case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    expect = case.get("expect", {})
    payload = result.get("payload", {})
    failures: list[str] = []

    if expect.get("status_code") is not None:
        if int(result.get("status_code", 0)) != int(expect["status_code"]):
            failures.append(f"status_code expected={expect['status_code']} actual={result.get('status_code')}")

    if expect.get("ok") is not None:
        if bool(result.get("ok", False)) != bool(expect["ok"]):
            failures.append(f"ok expected={expect['ok']} actual={result.get('ok')}")

    if "error_code" in expect:
        actual = payload.get("error_code") if isinstance(payload, dict) else None
        if actual != expect["error_code"]:
            failures.append(f"error_code expected={expect['error_code']} actual={actual}")

    for key in expect.get("contains_keys", []):
        if _get_nested(payload if isinstance(payload, dict) else {}, key) is None:
            failures.append(f"missing key: {key}")

    if "answer_regex" in expect:
        answer = ""
        if isinstance(payload, dict):
            answer = str(payload.get("answer", ""))
        if not re.search(str(expect["answer_regex"]), answer):
            failures.append("answer_regex not matched")

    if "stream_contains" in expect:
        raw = str(payload)
        for token in expect["stream_contains"]:
            if token not in raw:
                failures.append(f"stream token missing: {token}")

    if "pending_queue_min" in expect:
        queue = []
        if isinstance(payload, dict):
            queue = payload.get("action_pending_queue", []) or []
        if len(queue) < int(expect["pending_queue_min"]):
            failures.append(f"pending_queue_min expected>={expect['pending_queue_min']} actual={len(queue)}")

    if "action_status_in" in expect:
        status = None
        if isinstance(payload, dict):
            result_obj = payload.get("result", {})
            if isinstance(result_obj, dict):
                status = result_obj.get("status")
        if status not in set(expect["action_status_in"]):
            failures.append(f"action status {status} not in {expect['action_status_in']}")

    if "max_latency_ms" in expect:
        latency = int(result.get("latency_ms", 0))
        if latency > int(expect["max_latency_ms"]):
            failures.append(f"latency {latency}ms exceeds {expect['max_latency_ms']}ms")

    return failures
