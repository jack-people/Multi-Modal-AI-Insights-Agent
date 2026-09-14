import os
import tempfile
import unittest
from unittest.mock import patch

from memory.store import (
    load_user_profile,
    save_user_profile,
    load_memory_notes,
    append_memory_note,
)


class MemoryProfileTests(unittest.TestCase):
    def test_load_default_profile_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "profiles.json")
            with patch("memory.store.USER_PROFILE_STORE_PATH", store_path):
                profile = load_user_profile("session-a")
        self.assertEqual(profile["answer_style"], "balanced")
        self.assertEqual(profile["tone"], "professional")
        self.assertTrue(profile["use_structure"])

    def test_save_and_reload_profile(self):
        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "profiles.json")
            with patch("memory.store.USER_PROFILE_STORE_PATH", store_path):
                save_user_profile(
                    "session-b",
                    {"answer_style": "detailed", "tone": "casual", "use_structure": False},
                )
                profile = load_user_profile("session-b")
        self.assertEqual(profile["answer_style"], "detailed")
        self.assertEqual(profile["tone"], "casual")
        self.assertFalse(profile["use_structure"])

    def test_append_and_load_memory_notes(self):
        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "profiles.json")
            with patch("memory.store.USER_PROFILE_STORE_PATH", store_path):
                append_memory_note("session-c", "记住：我的目标是做科研助手。")
                append_memory_note("session-c", "记住：我的目标是做科研助手。")  # 去重
                append_memory_note("session-c", "以后默认中文回答。")
                notes = load_memory_notes("session-c")
        self.assertEqual(len(notes), 2)
        self.assertIn("以后默认中文回答。", notes)


if __name__ == "__main__":
    unittest.main()
