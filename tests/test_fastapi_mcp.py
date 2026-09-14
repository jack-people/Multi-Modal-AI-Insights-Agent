import unittest

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
        app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner()
        if not hasattr(app.state, "dsh_mcp"):
            self.skipTest("mcp package not installed; /v1/mcp not mounted")
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()
        self.app = app

    def tearDown(self):
        if getattr(self, "_cm", None):
            self._cm.__exit__(None, None, None)
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


if __name__ == "__main__":
    unittest.main()
