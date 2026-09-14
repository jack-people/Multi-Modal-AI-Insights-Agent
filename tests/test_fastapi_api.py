import unittest
try:
    from fastapi.testclient import TestClient
    from app.api.deps import get_agent_runner
    import app.api.main as api_main
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

    def stream_chat(self, session_id: str, req):
        yield {
            "schema": "mm-agent.stream.v1",
            "seq": 1,
            "ts": "2026-06-21T08:00:00+00:00",
            "type": "run_started",
            "session_id": session_id,
            "data": {"message": req.message},
        }
        yield {
            "schema": "mm-agent.stream.v1",
            "seq": 2,
            "ts": "2026-06-21T08:00:01+00:00",
            "type": "run_completed",
            "session_id": session_id,
            "data": {"answer": "done"},
        }

    def get_state(self, session_id: str):
        return {
            "session_id": session_id,
            "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
            "last_answer": "ok",
            "last_reasoning": "",
            "updated_at": "2026-06-21T08:00:00",
            "action_pending_queue": [],
            "action_execution_logs": [],
        }

    def confirm_action(self, session_id: str, action_id: str, approve: bool):
        return {"ok": False, "message": "action_id 不存在", "session_id": session_id}


class FastApiApiTests(unittest.TestCase):
    def setUp(self):
        if not FASTAPI_AVAILABLE:
            self.skipTest("fastapi/testclient not installed in current python environment")
        self._old_auth_enabled = api_main.API_AUTH_ENABLED
        self._old_auth_key = api_main.API_AUTH_KEY
        self._old_rate = api_main.API_RATE_LIMIT_PER_MIN

        api_main.API_AUTH_ENABLED = False
        api_main.API_AUTH_KEY = "test-api-key"
        api_main.API_RATE_LIMIT_PER_MIN = 100

        app = api_main.create_api_app()
        app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner()
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()
        self.app = app

    def tearDown(self):
        if getattr(self, "_cm", None):
            self._cm.__exit__(None, None, None)
        if getattr(self, "app", None):
            self.app.dependency_overrides.clear()
        api_main.API_AUTH_ENABLED = self._old_auth_enabled
        api_main.API_AUTH_KEY = self._old_auth_key
        api_main.API_RATE_LIMIT_PER_MIN = self._old_rate

    def test_healthz(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_chat_response(self):
        resp = self.client.post("/v1/sessions/demo/chat", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["session_id"], "demo")
        self.assertIn("echo:hello", body["answer"])

    def test_stream_response(self):
        resp = self.client.post("/v1/sessions/demo/stream", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("event: run_started", resp.text)
        self.assertIn("event: run_completed", resp.text)

    def test_action_not_found_is_404(self):
        resp = self.client.post("/v1/sessions/demo/actions/act_x/reject")
        self.assertEqual(resp.status_code, 404)
        body = resp.json()
        self.assertEqual(body["error_code"], "MM404_ACTION_NOT_FOUND")

    def test_validation_error_has_unified_shape(self):
        resp = self.client.post("/v1/sessions/demo/chat", json={"message": ""})
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body["error_code"], "MM422_VALIDATION_ERROR")
        self.assertFalse(body["ok"])

    def test_api_key_auth_enabled(self):
        api_main.API_AUTH_ENABLED = True
        app = api_main.create_api_app()
        app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner()
        with TestClient(app) as client:
            no_key_resp = client.post("/v1/sessions/demo/chat", json={"message": "hello"})
            self.assertEqual(no_key_resp.status_code, 401)
            self.assertEqual(no_key_resp.json()["error_code"], "MM401_UNAUTHORIZED")

            with_key_resp = client.post(
                "/v1/sessions/demo/chat",
                headers={"X-API-Key": "test-api-key"},
                json={"message": "hello"},
            )
            self.assertEqual(with_key_resp.status_code, 200)
        app.dependency_overrides.clear()

    def test_rate_limit(self):
        api_main.API_RATE_LIMIT_PER_MIN = 1
        app = api_main.create_api_app()
        app.dependency_overrides[get_agent_runner] = lambda: _FakeRunner()
        with TestClient(app) as client:
            first = client.post("/v1/sessions/demo/chat", json={"message": "first"})
            self.assertEqual(first.status_code, 200)
            second = client.post("/v1/sessions/demo/chat", json={"message": "second"})
            self.assertEqual(second.status_code, 429)
            self.assertEqual(second.json()["error_code"], "MM429_RATE_LIMITED")
        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
