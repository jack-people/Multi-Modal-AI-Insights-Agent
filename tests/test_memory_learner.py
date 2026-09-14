import unittest

from memory.learner import infer_profile_updates


class MemoryLearnerTests(unittest.TestCase):
    def test_infer_concise_and_structure(self):
        updates = infer_profile_updates("以后请回答简短一点，并且分点写。")
        self.assertEqual(updates.get("answer_style"), "concise")
        self.assertTrue(updates.get("use_structure"))

    def test_infer_detailed_and_casual(self):
        updates = infer_profile_updates("请详细展开，语气轻松一点。")
        self.assertEqual(updates.get("answer_style"), "detailed")
        self.assertEqual(updates.get("tone"), "casual")

    def test_infer_none_when_no_preference(self):
        updates = infer_profile_updates("帮我查一下最近多模态论文。")
        self.assertEqual(updates, {})


if __name__ == "__main__":
    unittest.main()
