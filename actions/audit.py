import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

try:
    from config import ACTION_AUDIT_LOG_PATH
except Exception:
    ACTION_AUDIT_LOG_PATH = os.getenv("ACTION_AUDIT_LOG_PATH", "audit.log")


def append_audit_log(
    action_name: str,
    risk: str,
    status: str,
    detail: str,
    meta: dict | None = None,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action_name,
        "risk": risk,
        "status": status,
        "detail": detail,
        "meta": meta or {},
    }
    parent = os.path.dirname(ACTION_AUDIT_LOG_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(ACTION_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
