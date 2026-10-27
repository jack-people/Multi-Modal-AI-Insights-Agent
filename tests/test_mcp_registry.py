import unittest

from mcp_tools.context import resolve_session_id
from mcp_tools.registry import DSH_HTTP_TOOL_NAMES, FULL_TOOL_NAMES, register_tools
from mcp_tools.service import McpService
from runtime_context import set_session_hint, set_request_id


class _FakeMcp:
    def __init__(self):
        self.names: list[str] = []

    def tool(self, name=None):
        def deco(fn):
            self.names.append(name)
            return fn

        return deco


class _FakeRunner:
    def __init__(self):
        self.states: dict[str, dict] = {}
        self.confirmed: list[tuple[str, str, bool]] = []

    def get_state(self, session_id: str):
        return self.states.get(session_id, {"session_id": session_id, "action_pending_queue": []})

    def request_action(self, session_id: str, action_name: str, risk: str, query: str, message: str, confirm_payload: dict):
        row = {"id": "act_test", "action": action_name, "risk": risk}
        self.states[session_id] = {"session_id": session_id, "action_pending_queue": [row]}
        return {"ok": True, "session_id": session_id, "status": "queued", "action_id": "act_test", "pending_action": row}

    def confirm_action(self, session_id: str, action_id: str, approve: bool):
        self.confirmed.append((session_id, action_id, approve))
        status = "executed" if approve else "rejected"
        return {"ok": True, "session_id": session_id, "action_id": action_id, "result": {"status": status}}


class McpRegistryTests(unittest.TestCase):
    def setUp(self):
        set_session_hint("")
        set_request_id("")

    def test_dsh_surface_excludes_chat_and_aliases(self):
        self.assertNotIn("chat", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("stream_chat", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("session_chat", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("action_request_shell_command", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("action_request_shell_command", FULL_TOOL_NAMES)
        self.assertNotIn("actions_request_shell_command", FULL_TOOL_NAMES)
        self.assertIn("chat", FULL_TOOL_NAMES)
        self.assertIn("paper_run_start", DSH_HTTP_TOOL_NAMES)

    def test_register_tools_include_filters(self):
        mcp = _FakeMcp()
        register_tools(mcp, McpService(runner=_FakeRunner()), include=DSH_HTTP_TOOL_NAMES)
        self.assertEqual(mcp.names, list(DSH_HTTP_TOOL_NAMES))
        self.assertNotIn("chat", mcp.names)

    def test_session_id_uses_header_then_default(self):
        self.assertEqual(resolve_session_id(None), "dsh-default")
        set_session_hint("from-header")
        self.assertEqual(resolve_session_id(None), "from-header")
        self.assertEqual(resolve_session_id("explicit"), "explicit")

    def test_optional_session_id_stays_aligned(self):
        set_session_hint("dsh-shared")
        set_request_id("req-1")
        service = McpService(runner=_FakeRunner())
        queued = service.action_request_write_file(filename="a.md", content="x")
        state = service.get_state()
        self.assertEqual(queued["session_id"], "dsh-shared")
        self.assertEqual(state["session_id"], "dsh-shared")
        self.assertEqual(len(state["action_pending_queue"]), 1)
        self.assertEqual(queued.get("request_id"), "req-1")

    def test_mcp_cannot_confirm_or_reject_shell(self):
        runner = _FakeRunner()
        runner.states["s"] = {
            "session_id": "s",
            "action_pending_queue": [
                {"id": "act_shell", "action": "action_run_shell_command", "risk": "high"},
            ],
        }
        service = McpService(runner=runner)
        confirmed = service.confirm_action(session_id="s", action_id="act_shell")
        rejected = service.reject_action(session_id="s", action_id="act_shell")
        self.assertFalse(confirmed["ok"])
        self.assertEqual(confirmed["error_code"], "MM403_SHELL_HUMAN_ONLY")
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error_code"], "MM403_SHELL_HUMAN_ONLY")
        self.assertEqual(runner.confirmed, [])
        self.assertEqual(len(runner.get_state("s")["action_pending_queue"]), 1)

    def test_mcp_can_still_confirm_non_shell(self):
        runner = _FakeRunner()
        runner.states["s"] = {
            "session_id": "s",
            "action_pending_queue": [
                {"id": "act_file", "action": "action_write_report_file", "risk": "low"},
            ],
        }
        service = McpService(runner=runner)
        result = service.confirm_action(session_id="s", action_id="act_file")
        self.assertTrue(result["ok"])
        self.assertEqual(runner.confirmed, [("s", "act_file", True)])


if __name__ == "__main__":
    unittest.main()
