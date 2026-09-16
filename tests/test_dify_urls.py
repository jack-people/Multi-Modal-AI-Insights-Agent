import unittest

from config import dify_api_root


class DifyUrlTests(unittest.TestCase):
    def test_cloud_base_without_v1(self):
        self.assertEqual(dify_api_root("https://api.dify.ai"), "https://api.dify.ai/v1")

    def test_cloud_base_already_has_v1(self):
        self.assertEqual(dify_api_root("https://api.dify.ai/v1"), "https://api.dify.ai/v1")
        self.assertEqual(dify_api_root("https://api.dify.ai/v1/"), "https://api.dify.ai/v1")

    def test_local_default(self):
        self.assertEqual(dify_api_root("http://localhost"), "http://localhost/v1")


if __name__ == "__main__":
    unittest.main()
