import unittest
from unittest.mock import patch

from voice.asr import transcribe_audio_bytes
from voice.tts import synthesize_speech


class _Resp:
    def __init__(self, status_code=200, json_payload=None, content=b""):
        self.status_code = status_code
        self._json_payload = json_payload or {}
        self.content = content
        self.text = str(self._json_payload)

    def json(self):
        return self._json_payload


class VoicePipelineTests(unittest.TestCase):
    def test_asr_disabled_fallback(self):
        with patch("voice.asr.VOICE_ENABLED", False):
            res = transcribe_audio_bytes(b"fake-audio", filename="a.wav")
        self.assertFalse(res["ok"])
        self.assertIn("未开启", res["error"])

    @patch("voice.asr.VOICE_ENABLED", True)
    @patch("voice.asr.VOICE_ASR_URL", "http://asr.local/v1/audio/transcriptions")
    @patch("voice.asr.VOICE_ASR_API_KEY", "k")
    @patch("voice.asr.requests.post")
    def test_asr_success(self, mock_post):
        mock_post.return_value = _Resp(status_code=200, json_payload={"text": "你好，世界"})
        res = transcribe_audio_bytes(b"fake-audio", filename="a.wav")
        self.assertTrue(res["ok"])
        self.assertEqual(res["text"], "你好，世界")

    @patch("voice.tts.VOICE_ENABLED", True)
    @patch("voice.tts.VOICE_TTS_URL", "http://tts.local/v1/audio/speech")
    @patch("voice.tts.VOICE_TTS_API_KEY", "k")
    @patch("voice.tts.requests.post")
    def test_tts_success(self, mock_post):
        mock_post.return_value = _Resp(status_code=200, content=b"mp3-bytes")
        res = synthesize_speech("测试")
        self.assertTrue(res["ok"])
        self.assertEqual(res["audio_bytes"], b"mp3-bytes")

    def test_tts_disabled_fallback(self):
        with patch("voice.tts.VOICE_ENABLED", False):
            res = synthesize_speech("测试")
        self.assertFalse(res["ok"])
        self.assertIn("未开启", res["error"])


if __name__ == "__main__":
    unittest.main()
