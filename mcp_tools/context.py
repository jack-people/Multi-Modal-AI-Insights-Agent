from runtime_context import get_request_id, get_session_hint, set_thread_id


def resolve_session_id(explicit: str | None = None) -> str:
    """会话对齐靠配置/请求头，不依赖模型每轮填同一个 session_id。"""
    text = str(explicit or "").strip()
    if text:
        set_thread_id(text)
        return text

    hint = str(get_session_hint() or "").strip()
    if hint:
        set_thread_id(hint)
        return hint

    try:
        from config import MM_MCP_DEFAULT_SESSION_ID
        fallback = MM_MCP_DEFAULT_SESSION_ID
    except Exception:
        fallback = "dsh-default"

    set_thread_id(fallback)
    return fallback


def attach_request_meta(payload: dict, session_id: str | None = None) -> dict:
    out = dict(payload)
    if session_id:
        out.setdefault("session_id", session_id)
    request_id = get_request_id()
    if request_id:
        out.setdefault("request_id", request_id)
    return out
