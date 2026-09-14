import requests
from model import VOICE_ASR_MODEL
from config import (
    VOICE_ENABLED,
    VOICE_TIMEOUT_SEC,
    VOICE_ASR_URL,
    VOICE_ASR_API_KEY,
    VOICE_ASR_LANGUAGE,
)
from runtime_context import log_event


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "voice.wav") -> dict:
    """调用 ASR 服务，将音频字节转成文本。"""
    if not VOICE_ENABLED:
        return {"ok": False, "text": "", "error": "语音能力未开启（VOICE_ENABLED=false）"}
    if not audio_bytes:
        return {"ok": False, "text": "", "error": "音频内容为空"}

    headers = {"Authorization": f"Bearer {VOICE_ASR_API_KEY}"}
    data = {"model": VOICE_ASR_MODEL, "language": VOICE_ASR_LANGUAGE}
    files = {"file": (filename, audio_bytes, "audio/wav")}

    try:
        log_event("voice_asr", "start", meta={"bytes": len(audio_bytes), "model": VOICE_ASR_MODEL})
        response = requests.post(
            VOICE_ASR_URL,
            headers=headers,
            data=data,
            files=files,
            timeout=VOICE_TIMEOUT_SEC,
        )
        if response.status_code != 200:
            error = f"ASR HTTP错误: {response.status_code} {response.text}"
            log_event("voice_asr", "error", meta={"error": error})
            return {"ok": False, "text": "", "error": error}

        payload = response.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            error = "ASR 未返回可用文本"
            log_event("voice_asr", "error", meta={"error": error})
            return {"ok": False, "text": "", "error": error}

        log_event("voice_asr", "done", meta={"chars": len(text)})
        return {"ok": True, "text": text, "error": ""}
    except Exception as e:
        error = f"ASR 调用异常: {e}"
        log_event("voice_asr", "error", meta={"error": str(e)})
        return {"ok": False, "text": "", "error": error}
