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

    def get_state(self, session_id: str):
        return self.states.get(session_id, {"session_id": session_id, "action_pending_queue": []})

    def request_action(self, session_id: str, action_name: str, risk: str, query: str, message: str, confirm_payload: dict):
        row = {"id": "act_test", "action": action_name, "risk": risk}
        self.states[session_id] = {"session_id": session_id, "action_pending_queue": [row]}
        return {"ok": True, "session_id": session_id, "status": "queued", "action_id": "act_test", "pending_action": row}


class McpRegistryTests(unittest.TestCase):
    def setUp(self):
        set_session_hint("")
        set_request_id("")

    def test_dsh_surface_excludes_chat_and_aliases(self):
        self.assertNotIn("chat", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("stream_chat", DSH_HTTP_TOOL_NAMES)
        self.assertNotIn("session_chat", DSH_HTTP_TOOL_NAMES)
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


if __name__ == "__main__":
    unittest.main()
