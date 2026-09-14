import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ========== DeepSeek / 核心 LLM 模型配置 ==========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "deepseek-chat")
SYNTHESIZER_MODEL = os.getenv("SYNTHESIZER_MODEL", "deepseek-reasoner")
ROUTER_TEMPERATURE = _env_float("ROUTER_TEMPERATURE", 0.1)
SYNTHESIZER_TEMPERATURE = _env_float("SYNTHESIZER_TEMPERATURE", 0.7)
SYNTHESIZER_MAX_TOKENS = _env_int("SYNTHESIZER_MAX_TOKENS", 4096)
MODEL_REQUEST_TIMEOUT_SEC = _env_int("MODEL_REQUEST_TIMEOUT_SEC", 60)
MODEL_MAX_RETRIES = _env_int("MODEL_MAX_RETRIES", 2)

# ========== 语音/视觉模型名配置 ==========
VOICE_ASR_MODEL = os.getenv("VOICE_ASR_MODEL", "whisper-1")
VOICE_TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "tts-1")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
