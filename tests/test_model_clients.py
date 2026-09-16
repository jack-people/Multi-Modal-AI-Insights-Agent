import unittest
from unittest.mock import patch

from model import clients


class LazyClientTests(unittest.TestCase):
    def test_import_does_not_construct_clients(self):
        self.assertIsNone(clients.llm_router._client)
        self.assertIsNone(clients.llm_synthesizer._client)

    def test_missing_key_raises_on_first_use(self):
        saved = clients.llm_router._client
        clients.llm_router._client = None
        try:
            with patch.object(clients, "DEEPSEEK_API_KEY", None):
                with self.assertRaises(RuntimeError) as ctx:
                    clients.llm_router.bind_tools([])
            self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))
            self.assertIsNone(clients.llm_router._client)
        finally:
            clients.llm_router._client = saved
