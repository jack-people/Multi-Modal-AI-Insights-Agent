import json
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any

_thread_id_ctx: ContextVar[str] = ContextVar("thread_id", default="unknown")


def set_thread_id(thread_id: str) -> None:
    _thread_id_ctx.set(thread_id or "unknown")


def get_thread_id() -> str:
    return _thread_id_ctx.get()


def log_event(node: str, event: str, retry_count: int = 0, meta: Optional[Dict[str, Any]] = None) -> None:
    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "thread_id": get_thread_id(),
        "node": node,
        "event": event,
        "retry_count": retry_count,
        "meta": meta or {}
    }
    print(json.dumps(payload, ensure_ascii=False))
