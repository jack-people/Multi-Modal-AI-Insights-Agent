import json
import unittest
from unittest.mock import patch

import tools


class _Resp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class DifyClientTests(unittest.TestCase):
    def setUp(self):
        tools._dify_mode_resolved = None

    def test_extract_chat_answer(self):
        self.assertEqual(tools.extract_dify_answer({"answer": "from chat"}), "from chat")

    def test_extract_workflow_outputs(self):
        self.assertEqual(
            tools.extract_dify_answer({"data": {"outputs": {"text": "from wf"}}}),
            "from wf",
        )

    def test_auto_retries_chat_after_not_workflow_app(self):
        workflow_err = _Resp(400, {"code": "not_workflow_app", "message": "mismatch", "status": 400})
        chat_ok = _Resp(200, {"answer": "kb hit"})
        with (
            patch.object(tools, "DIFY_APP_MODE", "auto"),
            patch.object(tools, "_request_with_retry", side_effect=[workflow_err, chat_ok]) as mocked,
        ):
            response, mode, error = tools.call_dify_search("multimodal VLM")
        self.assertEqual(mode, "chat")
        self.assertEqual(error, "")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked.call_count, 2)
        self.assertIn("/chat-messages", mocked.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
