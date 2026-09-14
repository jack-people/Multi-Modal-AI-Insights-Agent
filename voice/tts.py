import requests
from model import VOICE_TTS_MODEL
from config import (
    VOICE_ENABLED,
    VOICE_TIMEOUT_SEC,
    VOICE_TTS_URL,
    VOICE_TTS_API_KEY,
    VOICE_TTS_VOICE,
)
from runtime_context import log_event


def synthesize_speech(text: str) -> dict:
    """调用 TTS 服务，将文本转为音频字节。"""
    if not VOICE_ENABLED:
        return {"ok": False, "audio_bytes": b"", "error": "语音能力未开启（VOICE_ENABLED=false）"}
    if not text or not text.strip():
        return {"ok": False, "audio_bytes": b"", "error": "TTS 输入文本为空"}

    headers = {
        "Authorization": f"Bearer {VOICE_TTS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": VOICE_TTS_MODEL, "voice": VOICE_TTS_VOICE, "input": text}

    try:
        log_event("voice_tts", "start", meta={"chars": len(text), "model": VOICE_TTS_MODEL, "voice": VOICE_TTS_VOICE})
        response = requests.post(
            VOICE_TTS_URL,
            headers=headers,
            json=payload,
            timeout=VOICE_TIMEOUT_SEC,
        )
        if response.status_code != 200:
            error = f"TTS HTTP错误: {response.status_code} {response.text}"
            log_event("voice_tts", "error", meta={"error": error})
            return {"ok": False, "audio_bytes": b"", "error": error}

        audio_bytes = response.content or b""
        if not audio_bytes:
            error = "TTS 返回音频为空"
            log_event("voice_tts", "error", meta={"error": error})
            return {"ok": False, "audio_bytes": b"", "error": error}

        log_event("voice_tts", "done", meta={"bytes": len(audio_bytes)})
        return {"ok": True, "audio_bytes": audio_bytes, "error": ""}
    except Exception as e:
        error = f"TTS 调用异常: {e}"
        log_event("voice_tts", "error", meta={"error": str(e)})
        return {"ok": False, "audio_bytes": b"", "error": error}
