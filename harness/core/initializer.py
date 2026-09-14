import importlib.util
import json
import os
import platform
from datetime import datetime
from typing import Any

from harness.core.workspace import HarnessWorkspace


def _load_suite(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        suite = json.load(f)
    if not isinstance(suite, dict):
        raise ValueError("suite 文件必须是 JSON 对象")
    if not isinstance(suite.get("cases", []), list):
        raise ValueError("suite.cases 必须是数组")
    return suite


def _dependency_check() -> dict[str, Any]:
    checks = {}
    for mod in ["pydantic", "fastapi", "langchain", "langchain_core", "langchain_openai"]:
        checks[mod] = importlib.util.find_spec(mod) is not None
    return checks


def initialize_run(
    suite_path: str,
    api_base_url: str,
    report_dir: str,
    workspace_root: str = "harness/workspace",
    run_id: str | None = None,
) -> HarnessWorkspace:
    suite = _load_suite(suite_path)
    ws = HarnessWorkspace.create(workspace_root, run_id=run_id)

    manifest = {
        "run_id": ws.run_id,
        "created_at": datetime.now().isoformat(),
        "suite_path": suite_path,
        "suite_name": suite.get("suite", ""),
        "api_base_url": api_base_url,
        "report_dir": report_dir,
        "workspace_root": workspace_root,
    }
    ws.write_json("manifest.json", manifest)

    plan = {
        "suite": suite.get("suite", ""),
        "description": suite.get("description", ""),
        "cases": suite.get("cases", []),
    }
    ws.write_json("plan.json", plan)
    ws.write_json("context.json", {})

    env = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "dependency_check": _dependency_check(),
    }
    ws.write_json("environment.json", env)
    ws.mark_state("initialized")
    return ws
