import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime
from typing import Optional, Dict, Any, Iterator

_thread_id_ctx: ContextVar[str] = ContextVar("thread_id", default="unknown")
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_session_hint_ctx: ContextVar[str] = ContextVar("session_hint", default="")
_force_action_confirm_ctx: ContextVar[bool] = ContextVar("force_action_confirm", default=False)


def set_thread_id(thread_id: str) -> None:
    _thread_id_ctx.set(thread_id or "unknown")


def get_thread_id() -> str:
    return _thread_id_ctx.get()


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id or "")


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_session_hint(session_id: str) -> None:
    _session_hint_ctx.set(session_id or "")


def get_session_hint() -> str:
    return _session_hint_ctx.get()


def set_force_action_confirm(enabled: bool) -> Token:
    return _force_action_confirm_ctx.set(bool(enabled))


def is_force_action_confirm() -> bool:
    return _force_action_confirm_ctx.get()


@contextmanager
def action_confirm_required() -> Iterator[None]:
    token = set_force_action_confirm(True)
    try:
        yield
    finally:
        _force_action_confirm_ctx.reset(token)


def log_event(node: str, event: str, retry_count: int = 0, meta: Optional[Dict[str, Any]] = None) -> None:
    extra = dict(meta or {})
    request_id = get_request_id()
    if request_id and "request_id" not in extra:
        extra["request_id"] = request_id
    payload = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "thread_id": get_thread_id(),
        "node": node,
        "event": event,
        "retry_count": retry_count,
        "meta": extra,
    }
    print(json.dumps(payload, ensure_ascii=False))
