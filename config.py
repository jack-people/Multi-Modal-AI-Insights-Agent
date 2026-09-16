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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def dify_api_root(base_url: str) -> str:
    """DIFY_BASE_URL 写成带或不带 /v1 都能拼出正确的 API 根路径。"""
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"

# ========== Dify 配置 ==========
DIFY_APP_API_KEY = os.getenv("DIFY_APP_API_KEY")
DIFY_DATASET_API_KEY = os.getenv("DIFY_DATASET_API_KEY")
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "http://localhost")
_dify_root = dify_api_root(DIFY_BASE_URL)
DATASET_ID = os.getenv("DIFY_DATASET_ID", "7f5cbb69-1ff7-4f2e-a3bd-baaddf10847c")
DIFY_APP_MODE = os.getenv("DIFY_APP_MODE", "auto").strip().lower() or "auto"
DIFY_WORKFLOW_URL = os.getenv("DIFY_WORKFLOW_URL", "").strip() or f"{_dify_root}/workflows/run"
DIFY_CHAT_URL = os.getenv("DIFY_CHAT_URL", "").strip() or f"{_dify_root}/chat-messages"
DIFY_COMPLETION_URL = os.getenv("DIFY_COMPLETION_URL", "").strip() or f"{_dify_root}/completion-messages"
DIFY_RETRIEVAL_URL = os.getenv("DIFY_RETRIEVAL_URL", "").strip() or f"{_dify_root}/datasets/{DATASET_ID}/retrieve"
# Dify blocking 调用经常超过通用工具超时；系统代理也容易把 api.dify.ai 的 TLS 掐断
DIFY_TIMEOUT_SEC = _env_int("DIFY_TIMEOUT_SEC", 60)
DIFY_HTTP_TRUST_ENV = _env_bool("DIFY_HTTP_TRUST_ENV", True)

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
MM_MCP_DEFAULT_SESSION_ID = os.getenv("MM_MCP_DEFAULT_SESSION_ID", "dsh-default").strip() or "dsh-default"

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
    if DIFY_APP_MODE not in {"auto", "workflow", "chat", "completion"}:
        errors.append("DIFY_APP_MODE 必须是 auto/workflow/chat/completion 之一")
    if not _is_valid_http_url(DIFY_WORKFLOW_URL):
        errors.append(f"DIFY_WORKFLOW_URL 非法: {DIFY_WORKFLOW_URL}")
    if not _is_valid_http_url(DIFY_CHAT_URL):
        errors.append(f"DIFY_CHAT_URL 非法: {DIFY_CHAT_URL}")

    db_error = _validate_db_writable(AGENT_DB_PATH)
    if db_error:
        errors.append(db_error)

    if TOOL_TIMEOUT_SEC <= 0:
        errors.append("TOOL_TIMEOUT_SEC 必须大于 0")
    if DIFY_TIMEOUT_SEC <= 0:
        errors.append("DIFY_TIMEOUT_SEC 必须大于 0")
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
    if ACTION_AUTO_EXECUTE_MAX_RISK not in {"none", "low", "medium", "high"}:
        errors.append("ACTION_AUTO_EXECUTE_MAX_RISK 必须是 none/low/medium/high 之一")

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
