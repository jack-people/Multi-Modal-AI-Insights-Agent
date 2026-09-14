from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunConfig:
    suite_path: str
    api_base_url: str = "http://127.0.0.1:8001"
    report_dir: str = "harness/report"
    workspace_root: str = "harness/workspace"
    run_id: str | None = None


@dataclass
class CaseOutcome:
    id: str
    entry: str
    action: str
    passed: bool
    status_code: int
    latency_ms: int
    failures: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
