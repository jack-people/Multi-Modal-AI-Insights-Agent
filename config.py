# 配置与模型初始化
import os
import sqlite3
from urllib.parse import urlparse
from typing import Optional
from dotenv import load_dotenv
from model import DEEPSEEK_API_KEY, VISION_MODEL, VOICE_ASR_MODEL, VOICE_TTS_MODEL

load_dotenv()

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# ========== Dify 配置 ==========
DIFY_APP_API_KEY = os.getenv("DIFY_APP_API_KEY")
DIFY_DATASET_API_KEY = os.getenv("DIFY_DATASET_API_KEY")
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "http://localhost")
DIFY_WORKFLOW_URL = os.getenv("DIFY_WORKFLOW_URL", f"{DIFY_BASE_URL}/v1/workflows/run")
DATASET_ID = os.getenv("DIFY_DATASET_ID", "7f5cbb69-1ff7-4f2e-a3bd-baaddf10847c")
DIFY_RETRIEVAL_URL = os.getenv(
    "DIFY_RETRIEVAL_URL",
    f"{DIFY_BASE_URL}/v1/datasets/{DATASET_ID}/retrieve"
)

# ========== Agent 行为配置 ==========
MAX_CRITIC_RETRIES = _env_int("MAX_CRITIC_RETRIES", 3)
AGENT_DB_PATH = os.getenv("AGENT_DB_PATH", "databank/agent_chat_history.db")

# ========== API 网关配置（FastAPI WeekD） ==========
API_AUTH_ENABLED = _env_bool("API_AUTH_ENABLED", False)
API_AUTH_KEY = os.getenv("API_AUTH_KEY", "")
API_RATE_LIMIT_PER_MIN = _env_int("API_RATE_LIMIT_PER_MIN", 60)
API_CORS_ORIGINS = [
    item.strip()
    for item in os.getenv("API_CORS_ORIGINS", "*").split(",")
    if item.strip()
] or ["*"]

# ========== 工具调用稳定性配置 ==========
TOOL_TIMEOUT_SEC = _env_int("TOOL_TIMEOUT_SEC", 15)
TOOL_RETRY_MAX = _env_int("TOOL_RETRY_MAX", 3)
TOOL_RETRY_BACKOFF = _env_float("TOOL_RETRY_BACKOFF", 1.0)

# ========== 语音能力配置 ==========
VOICE_ENABLED = _env_bool("VOICE_ENABLED", False)
VOICE_TIMEOUT_SEC = _env_int("VOICE_TIMEOUT_SEC", 30)

VOICE_ASR_URL = os.getenv("VOICE_ASR_URL", "")
VOICE_ASR_API_KEY = os.getenv("VOICE_ASR_API_KEY", "")
VOICE_ASR_LANGUAGE = os.getenv("VOICE_ASR_LANGUAGE", "zh")

VOICE_TTS_URL = os.getenv("VOICE_TTS_URL", "")
VOICE_TTS_API_KEY = os.getenv("VOICE_TTS_API_KEY", "")
VOICE_TTS_VOICE = os.getenv("VOICE_TTS_VOICE", "alloy")
VOICE_AUTO_TTS_DEFAULT = _env_bool("VOICE_AUTO_TTS_DEFAULT", True)

# ========== 视觉能力配置 ==========
VISION_ENABLED = _env_bool("VISION_ENABLED", False)
VISION_TIMEOUT_SEC = _env_int("VISION_TIMEOUT_SEC", 45)
VISION_API_URL = os.getenv("VISION_API_URL", "")
VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_AUTO_ANALYZE_DEFAULT = _env_bool("VISION_AUTO_ANALYZE_DEFAULT", True)

# ========== 行动能力配置（Week6） ==========
ACTION_AUDIT_LOG_PATH = os.getenv("ACTION_AUDIT_LOG_PATH", "audit.log")
ACTION_AUTO_EXECUTE_MAX_RISK = os.getenv("ACTION_AUTO_EXECUTE_MAX_RISK", "low").strip().lower()

# ========== 用户偏好记忆配置（Week7） ==========
USER_PROFILE_STORE_PATH = os.getenv("USER_PROFILE_STORE_PATH", "databank/user_profiles.json")


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_db_writable(db_path: str) -> Optional[str]:
    try:
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS _healthcheck (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        return None
    except Exception as e:
        return f"SQLite 路径不可写: {db_path}，错误: {e}"


def validate_config(strict: bool = True) -> list[str]:
    errors = []

    if not DEEPSEEK_API_KEY:
        errors.append("缺少 DEEPSEEK_API_KEY")
    if not DIFY_APP_API_KEY:
        errors.append("缺少 DIFY_APP_API_KEY")
    if not _is_valid_http_url(DIFY_WORKFLOW_URL):
        errors.append(f"DIFY_WORKFLOW_URL 非法: {DIFY_WORKFLOW_URL}")

    db_error = _validate_db_writable(AGENT_DB_PATH)
    if db_error:
        errors.append(db_error)

    if TOOL_TIMEOUT_SEC <= 0:
        errors.append("TOOL_TIMEOUT_SEC 必须大于 0")
    if TOOL_RETRY_MAX < 1:
        errors.append("TOOL_RETRY_MAX 必须大于等于 1")
    if TOOL_RETRY_BACKOFF < 0:
        errors.append("TOOL_RETRY_BACKOFF 不能小于 0")
    if API_RATE_LIMIT_PER_MIN < 1:
        errors.append("API_RATE_LIMIT_PER_MIN 必须大于等于 1")
    if API_AUTH_ENABLED and not API_AUTH_KEY:
        errors.append("API_AUTH_ENABLED=true 时缺少 API_AUTH_KEY")
    if VOICE_TIMEOUT_SEC <= 0:
        errors.append("VOICE_TIMEOUT_SEC 必须大于 0")
    if VISION_TIMEOUT_SEC <= 0:
        errors.append("VISION_TIMEOUT_SEC 必须大于 0")
    if ACTION_AUTO_EXECUTE_MAX_RISK not in {"low", "medium", "high"}:
        errors.append("ACTION_AUTO_EXECUTE_MAX_RISK 必须是 low/medium/high 之一")

    if VOICE_ENABLED:
        if not _is_valid_http_url(VOICE_ASR_URL):
            errors.append(f"VOICE_ASR_URL 非法: {VOICE_ASR_URL}")
        if not _is_valid_http_url(VOICE_TTS_URL):
            errors.append(f"VOICE_TTS_URL 非法: {VOICE_TTS_URL}")
        if not VOICE_ASR_API_KEY:
            errors.append("VOICE_ENABLED=true 时缺少 VOICE_ASR_API_KEY")
        if not VOICE_TTS_API_KEY:
            errors.append("VOICE_ENABLED=true 时缺少 VOICE_TTS_API_KEY")

    if VISION_ENABLED:
        if not _is_valid_http_url(VISION_API_URL):
            errors.append(f"VISION_API_URL 非法: {VISION_API_URL}")
        if not VISION_API_KEY:
            errors.append("VISION_ENABLED=true 时缺少 VISION_API_KEY")

    if errors:
        message = "配置校验失败:\n- " + "\n- ".join(errors)
        if strict:
            raise RuntimeError(message)
        print(f"⚠️ {message}")

    return errors
