import json
import os
import tempfile
import unittest
from unittest.mock import patch

from actions.policy import should_auto_execute, normalize_risk
from actions.audit import append_audit_log
from actions.handlers import execute_confirmed_action


class ActionsRuntimeTests(unittest.TestCase):
    def test_risk_policy_order(self):
        self.assertTrue(should_auto_execute("low", "low"))
        self.assertTrue(should_auto_execute("low", "medium"))
        self.assertFalse(should_auto_execute("medium", "low"))
        self.assertFalse(should_auto_execute("high", "medium"))
        self.assertFalse(should_auto_execute("low", "none"))
        self.assertFalse(should_auto_execute("high", "none"))
        self.assertEqual(normalize_risk("UNKNOWN"), "high")

    def test_append_audit_log(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "audit.log")
            with patch("actions.audit.ACTION_AUDIT_LOG_PATH", log_path):
                append_audit_log(
                    action_name="action_write_report_file",
                    risk="low",
                    status="executed",
                    detail="ok",
                    meta={"file": "x.md"},
                )
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("action_write_report_file", content)
            self.assertIn("\"status\": \"executed\"", content)

    def test_execute_confirmed_action_write_report(self):
        with tempfile.TemporaryDirectory() as td:
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                res = execute_confirmed_action(
                    "action_write_report_file",
                    {"filename": "report.md", "content": "hello"},
                )
                self.assertTrue(res["ok"])
                self.assertTrue(os.path.exists(os.path.join(td, "action_outputs", "report.md")))
            finally:
                os.chdir(old_cwd)

    @patch("tools._allow_auto_execute", return_value=True)
    @patch("tools.append_audit_log")
    @patch("tools.log_event")
    @patch("actions.handlers.subprocess.run")
    def test_shell_tool_never_auto_executes(self, run, _log, _audit, _allow):
        from tools import action_run_shell_command

        raw = action_run_shell_command.invoke({"command": "echo hi"})
        payload = json.loads(raw)
        data = json.loads(payload["data"])
        self.assertEqual(data["status"], "pending_confirmation")
        self.assertTrue(data["requires_confirmation"])
        self.assertEqual(data["confirm_payload"]["command"], "echo hi")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
