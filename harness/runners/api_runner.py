import json
import time
import urllib.request
import urllib.error
from typing import Any

from .base import HarnessRunner


class ApiRunner(HarnessRunner):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                try:
                    return resp.getcode(), json.loads(text)
                except Exception:
                    return resp.getcode(), text
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(text)
            except Exception:
                return e.code, text

    def run_case(self, case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action = case.get("action", "")
        session_id = str(case.get("session_id", "demo"))
        t0 = time.perf_counter()

        if action == "healthz":
            status_code, payload = self._request("GET", "/healthz")
        elif action == "chat":
            status_code, payload = self._request(
                "POST",
                f"/v1/sessions/{session_id}/chat",
                {"message": case.get("message", "")},
            )
        elif action == "state":
            status_code, payload = self._request("GET", f"/v1/sessions/{session_id}/state")
        elif action == "stream_chat":
            status_code, payload = self._request(
                "POST",
                f"/v1/sessions/{session_id}/stream",
                {"message": case.get("message", "")},
            )
            if isinstance(payload, str):
                payload = {"raw_text": payload}
        elif action == "confirm_action":
            action_id = str(case.get("action_id") or context.get("last_action_id", ""))
            status_code, payload = self._request("POST", f"/v1/sessions/{session_id}/actions/{action_id}/confirm")
        elif action == "reject_action":
            action_id = str(case.get("action_id") or context.get("last_action_id", ""))
            status_code, payload = self._request("POST", f"/v1/sessions/{session_id}/actions/{action_id}/reject")
        else:
            status_code, payload = 400, {"ok": False, "error": f"unsupported api action: {action}"}

        latency_ms = int((time.perf_counter() - t0) * 1000)
        ok = status_code < 400
        return {
            "ok": ok,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "payload": payload,
        }
