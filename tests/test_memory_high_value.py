import unittest

from memory.high_value import extract_high_value_memory


class MemoryHighValueTests(unittest.TestCase):
    def test_extract_high_value_when_triggered(self):
        note = extract_high_value_memory("请记住：我主要做多模态方向，长期目标是做贾维斯助手。")
        self.assertTrue(note.startswith("请记住"))

    def test_skip_non_high_value(self):
        note = extract_high_value_memory("帮我查一下最近论文。")
        self.assertEqual(note, "")


if __name__ == "__main__":
    unittest.main()
