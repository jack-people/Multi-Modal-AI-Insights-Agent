import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from app.api.deps import get_agent_runner
    import app.api.main as api_main
    from mcp_tools.registry import DSH_HTTP_TOOL_NAMES

    FASTAPI_AVAILABLE = True
except Exception:
    FASTAPI_AVAILABLE = False


class _FakeRunner:
    def run_chat(self, session_id: str, req):
        return {
            "session_id": session_id,
            "last_answer": f"echo:{req.message}",
            "last_reasoning": "",
            "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
        }

    def get_state(self, session_id: str):
        return {
            "session_id": session_id,
            "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
            "last_answer": "",
            "last_reasoning": "",
            "updated_at": "",
            "action_pending_queue": [],
            "action_execution_logs": [],
        }

    def request_action(self, **kwargs):
        return {"ok": True, "session_id": kwargs.get("session_id"), "status": "queued", "action_id": "act_x"}

    def confirm_action(self, session_id: str, action_id: str, approve: bool):
        return {"ok": True, "session_id": session_id, "action_id": action_id, "approved": approve}


class FastApiMcpTests(unittest.TestCase):
    def setUp(self):
        if not FASTAPI_AVAILABLE:
            self.skipTest("fastapi not installed")
        self._old_auth_enabled = api_main.API_AUTH_ENABLED
        api_main.API_AUTH_ENABLED = False
        app = api_main.create_api_app()
        fake_runner = _FakeRunner()
        # REST 路由走 Depends，MCP 工具里的 McpService.runner 直接调 get_agent_runner，两处都要替换
        app.dependency_overrides[get_agent_runner] = lambda: fake_runner
        self._runner_patch = patch("mcp_tools.service.get_agent_runner", return_value=fake_runner)
        self._runner_patch.start()
        # MCP 的 DNS rebinding 防护只放行 localhost/127.0.0.1，默认 testserver 会 421
        self._cm = TestClient(app, base_url="http://127.0.0.1:8001")
        self.client = self._cm.__enter__()
        self.app = app

    def tearDown(self):
        if getattr(self, "_cm", None):
            self._cm.__exit__(None, None, None)
        if getattr(self, "_runner_patch", None):
            self._runner_patch.stop()
        if getattr(self, "app", None):
            self.app.dependency_overrides.clear()
        if FASTAPI_AVAILABLE:
            api_main.API_AUTH_ENABLED = self._old_auth_enabled

    def test_mcp_endpoint_mounted(self):
        resp = self.client.get("/v1/mcp")
        self.assertNotEqual(resp.status_code, 404)
        self.assertTrue(resp.headers.get("X-Request-Id"))

    def test_dsh_tool_names(self):
        mcp = self.app.state.dsh_mcp
        listed = [t.name for t in mcp._tool_manager.list_tools()]
        self.assertEqual(sorted(listed), sorted(DSH_HTTP_TOOL_NAMES))
        self.assertNotIn("chat", listed)

    def test_rest_chat_still_works(self):
        resp = self.client.post("/v1/sessions/demo/chat", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("echo:hello", resp.json()["answer"])

    def test_tool_call_sees_per_request_headers(self):
        """每次 tools/call 自带的 X-Request-Id / X-Session-Id 要进到工具结果里，而不是 initialize 那次的。"""
        import json

        accept = {"Accept": "application/json, text/event-stream"}

        def rpc(client, payload, **extra_headers):
            resp = client.post("/v1/mcp", json=payload, headers={**accept, **extra_headers})
            self.assertEqual(resp.status_code, 200, resp.text)
            data_line = next(line for line in resp.text.splitlines() if line.startswith("data: "))
            return json.loads(data_line[len("data: "):])["result"]

        client = self.client
        resp = client.post(
            "/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
            },
            headers={**accept, "X-Request-Id": "req-init", "X-Session-Id": "sess-init"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        mcp_sid = {"mcp-session-id": resp.headers["mcp-session-id"]}
        client.post("/v1/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers={**accept, **mcp_sid})

        result = rpc(
            client,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_state", "arguments": {}}},
            **mcp_sid,
            **{"X-Request-Id": "req-call-2", "X-Session-Id": "sess-call"},
        )
        state = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        self.assertEqual(state["request_id"], "req-call-2")
        self.assertEqual(state["session_id"], "sess-call")

        # 不带 X-Session-Id 时退回 mcp-session-id，request_id 退回 JSON-RPC id
        result = rpc(
            client,
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_state", "arguments": {}}},
            **mcp_sid,
        )
        state = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        self.assertEqual(state["session_id"], mcp_sid["mcp-session-id"])
        self.assertEqual(state["request_id"], "3")


if __name__ == "__main__":
    unittest.main()
