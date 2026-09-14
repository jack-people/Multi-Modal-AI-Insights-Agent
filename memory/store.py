import json
import os
from dotenv import load_dotenv

load_dotenv()

try:
    from config import USER_PROFILE_STORE_PATH
except Exception:
    USER_PROFILE_STORE_PATH = os.getenv("USER_PROFILE_STORE_PATH", "databank/user_profiles.json")


DEFAULT_PROFILE = {
    "answer_style": "balanced",   # concise / balanced / detailed
    "tone": "professional",       # professional / casual
    "use_structure": True,        # 是否偏好结构化分点
}
MAX_MEMORY_NOTES = 50


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_all_profiles() -> dict:
    if not os.path.exists(USER_PROFILE_STORE_PATH):
        return {}
    try:
        with open(USER_PROFILE_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def _save_all_profiles(data: dict) -> None:
    _ensure_parent(USER_PROFILE_STORE_PATH)
    with open(USER_PROFILE_STORE_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


def _normalize_thread_record(record: dict) -> dict:
    # 兼容旧格式：thread_id 直接存 profile 字段
    if not isinstance(record, dict):
        return {"profile": dict(DEFAULT_PROFILE), "memory_notes": []}
    if "profile" in record or "memory_notes" in record:
        profile = dict(DEFAULT_PROFILE)
        if isinstance(record.get("profile"), dict):
            profile.update(record["profile"])
        notes = record.get("memory_notes", [])
        if not isinstance(notes, list):
            notes = []
        return {"profile": profile, "memory_notes": [str(x).strip() for x in notes if str(x).strip()][:MAX_MEMORY_NOTES]}
    profile = dict(DEFAULT_PROFILE)
    profile.update(record)
    return {"profile": profile, "memory_notes": []}


def load_user_profile(thread_id: str) -> dict:
    all_profiles = _load_all_profiles()
    record = _normalize_thread_record(all_profiles.get(thread_id, {}))
    return record["profile"]


def save_user_profile(thread_id: str, profile: dict) -> dict:
    all_profiles = _load_all_profiles()
    record = _normalize_thread_record(all_profiles.get(thread_id, {}))
    merged = dict(DEFAULT_PROFILE)
    if isinstance(profile, dict):
        merged.update(profile)
    record["profile"] = merged
    all_profiles[thread_id] = record
    _save_all_profiles(all_profiles)
    return merged


def load_memory_notes(thread_id: str) -> list[str]:
    all_profiles = _load_all_profiles()
    record = _normalize_thread_record(all_profiles.get(thread_id, {}))
    return record["memory_notes"]


def load_thread_memory(thread_id: str) -> dict:
    """一次读取同一 thread 的 profile 与 memory_notes，减少重复 IO。"""
    all_profiles = _load_all_profiles()
    record = _normalize_thread_record(all_profiles.get(thread_id, {}))
    return {"profile": record["profile"], "memory_notes": record["memory_notes"]}


def append_memory_note(thread_id: str, note: str) -> list[str]:
    text = str(note or "").strip()
    if not text:
        return load_memory_notes(thread_id)

    all_profiles = _load_all_profiles()
    record = _normalize_thread_record(all_profiles.get(thread_id, {}))
    notes = record["memory_notes"]
    if text not in notes:
        notes.append(text)
    notes = notes[-MAX_MEMORY_NOTES:]
    record["memory_notes"] = notes
    all_profiles[thread_id] = record
    _save_all_profiles(all_profiles)
    return notes
