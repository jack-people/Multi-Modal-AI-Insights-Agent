import unittest
from unittest.mock import patch

from vision.analyzer import analyze_image_bytes


class _Resp:
    def __init__(self, status_code=200, json_payload=None):
        self.status_code = status_code
        self._json_payload = json_payload or {}
        self.text = str(self._json_payload)

    def json(self):
        return self._json_payload


class VisionPipelineTests(unittest.TestCase):
    def test_vision_disabled_fallback(self):
        with patch("vision.analyzer.VISION_ENABLED", False):
            res = analyze_image_bytes(b"img-bytes", mime_type="image/png", prompt="describe")
        self.assertFalse(res["ok"])
        self.assertIn("未开启", res["error"])

    @patch("vision.analyzer.VISION_ENABLED", True)
    @patch("vision.analyzer.VISION_API_URL", "http://vision.local/v1/chat/completions")
    @patch("vision.analyzer.VISION_API_KEY", "k")
    @patch("vision.analyzer.requests.post")
    def test_vision_success(self, mock_post):
        mock_post.return_value = _Resp(
            status_code=200,
            json_payload={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"raw_summary":"图中有一只猫和一张桌子。","ocr_text":"A1 B2",'
                                '"key_points":["猫在桌边"],"chart_insights":[],"uncertainties":[]}'
                            )
                        }
                    }
                ]
            },
        )
        res = analyze_image_bytes(b"img-bytes", mime_type="image/png", prompt="describe")
        self.assertTrue(res["ok"])
        self.assertIn("猫", res["text"])
        self.assertIn("[VISION_MODE=general]", res["text"])
        self.assertEqual(res["ocr_text"], "A1 B2")
        self.assertEqual(res["key_points"], ["猫在桌边"])

    @patch("vision.analyzer.VISION_ENABLED", True)
    @patch("vision.analyzer.VISION_API_URL", "http://vision.local/v1/chat/completions")
    @patch("vision.analyzer.VISION_API_KEY", "k")
    @patch("vision.analyzer.requests.post")
    def test_vision_chart_mode_prompt(self, mock_post):
        mock_post.return_value = _Resp(
            status_code=200,
            json_payload={"choices": [{"message": {"content": "图表显示模型A优于模型B。"}}]},
        )
        res = analyze_image_bytes(b"img-bytes", mime_type="image/png", mode="chart")
        self.assertTrue(res["ok"])
        self.assertIn("[VISION_MODE=chart]", res["text"])
        called_json = mock_post.call_args.kwargs["json"]
        content_items = called_json["messages"][0]["content"]
        self.assertIn("图表", content_items[0]["text"])


if __name__ == "__main__":
    unittest.main()
