import json
import os
from datetime import datetime
from typing import Any


class HarnessWorkspace:
    def __init__(self, root_dir: str, run_id: str):
        self.root_dir = root_dir
        self.run_id = run_id
        self.run_dir = os.path.join(root_dir, run_id)

    @staticmethod
    def new_run_id() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @classmethod
    def create(cls, root_dir: str, run_id: str | None = None) -> "HarnessWorkspace":
        rid = run_id or cls.new_run_id()
        ws = cls(root_dir=root_dir, run_id=rid)
        os.makedirs(ws.run_dir, exist_ok=True)
        return ws

    @classmethod
    def open(cls, root_dir: str, run_id: str) -> "HarnessWorkspace":
        ws = cls(root_dir=root_dir, run_id=run_id)
        if not os.path.isdir(ws.run_dir):
            raise FileNotFoundError(f"workspace run not found: {ws.run_dir}")
        return ws

    def _path(self, name: str) -> str:
        return os.path.join(self.run_dir, name)

    def write_json(self, name: str, data: dict[str, Any]) -> None:
        with open(self._path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def write_text(self, name: str, content: str) -> None:
        with open(self._path(name), "w", encoding="utf-8") as f:
            f.write(content)

    def read_json(self, name: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self._path(name)
        if not os.path.exists(path):
            return default or {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def append_jsonl(self, name: str, row: dict[str, Any]) -> None:
        with open(self._path(name), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def read_jsonl(self, name: str) -> list[dict[str, Any]]:
        path = self._path(name)
        if not os.path.exists(path):
            return []
        rows: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except Exception:
                    continue
        return rows

    def mark_state(self, state: str, extra: dict[str, Any] | None = None) -> None:
        payload = self.read_json("status.json", default={})
        payload.update(
            {
                "state": state,
                "updated_at": datetime.now().isoformat(),
            }
        )
        if extra:
            payload.update(extra)
        self.write_json("status.json", payload)
