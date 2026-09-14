import logging
import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def is_debug_enabled() -> bool:
    return _to_bool(os.getenv("DEBUG_LOG_ENABLED"), default=False)


def setup_logger(name: str = "multiModal_agent") -> logging.Logger:
    """
    更灵活的日志方案：
    - DEBUG_LOG_ENABLED=true 时开启日志输出
    - AGENT_LOG_LEVEL 可选覆盖级别（DEBUG/INFO/WARNING/ERROR）
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    debug_enabled = is_debug_enabled()
    explicit_level = os.getenv("AGENT_LOG_LEVEL")
    if not debug_enabled and not explicit_level:
        logger.disabled = True
        logger.addHandler(logging.NullHandler())
        return logger

    raw_level = (explicit_level or ("INFO" if debug_enabled else "WARNING")).upper()
    level = getattr(logging, raw_level, logging.INFO if debug_enabled else logging.WARNING)

    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
