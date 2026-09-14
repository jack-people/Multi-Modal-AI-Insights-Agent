import unittest

from memory.retriever import select_relevant_memory_notes


class MemoryRetrieverTests(unittest.TestCase):
    def test_select_relevant_by_overlap(self):
        notes = [
            "我主要做多模态科研方向。",
            "以后输出尽量简洁。",
            "我的长期目标是做贾维斯助手。",
        ]
        selected = select_relevant_memory_notes(notes, "帮我规划多模态科研路线", top_k=2)
        self.assertTrue(selected)
        self.assertIn("多模态", selected[0])

    def test_fallback_recent_when_no_overlap(self):
        notes = ["记住A", "记住B", "记住C"]
        selected = select_relevant_memory_notes(notes, "天气怎么样", top_k=2)
        self.assertEqual(selected, ["记住B", "记住C"])


if __name__ == "__main__":
    unittest.main()
