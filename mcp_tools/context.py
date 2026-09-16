from config import MM_MCP_DEFAULT_SESSION_ID
from runtime_context import get_request_id, get_session_hint, set_thread_id


def resolve_session_id(explicit: str | None = None) -> str:
    """会话对齐靠显式参数 → 请求头 → 配置缺省，不依赖模型每轮填同一个 session_id。"""
    sid = str(explicit or "").strip() or str(get_session_hint() or "").strip() or MM_MCP_DEFAULT_SESSION_ID
    set_thread_id(sid)
    return sid


def attach_request_meta(payload: dict, session_id: str | None = None) -> dict:
    out = dict(payload)
    if session_id:
        out.setdefault("session_id", session_id)
    request_id = get_request_id()
    if request_id:
        out.setdefault("request_id", request_id)
    return out
