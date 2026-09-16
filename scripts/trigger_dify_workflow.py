import json
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _build_inputs() -> dict[str, Any]:
    """
    可选通过 DIFY_WORKFLOW_INPUTS_JSON 注入工作流 inputs。
    例如：
    {"task":"daily_multimodal_report","paper_limit":10,"news_limit":0}
    """
    raw = _env("DIFY_WORKFLOW_INPUTS_JSON", "{}")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def main() -> int:
    base_url = _env("DIFY_BASE_URL", "http://localhost")
    api_key = _env("DIFY_APP_API_KEY")
    user_id = _env("DIFY_USER_ID", "multi-modal-agent-scheduler")
    timeout_sec = int(_env("DIFY_TRIGGER_TIMEOUT_SEC", "90") or "90")
    max_retries = int(_env("DIFY_TRIGGER_RETRIES", "2") or "2")
    retry_backoff = float(_env("DIFY_TRIGGER_BACKOFF_SEC", "2") or "2")

    if not api_key:
        print("[ERROR] 缺少 DIFY_APP_API_KEY")
        return 1

    root = base_url.rstrip("/")
    if not root.endswith("/v1"):
        root = f"{root}/v1"
    url = f"{root}/workflows/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": _build_inputs(),
        "response_mode": "blocking",
        "user": user_id,
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] 触发 Dify Workflow: attempt={attempt}/{max_retries}")
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            body = resp.json()
            run_id = body.get("workflow_run_id", "")
            status = body.get("data", {}).get("status", "")
            outputs = body.get("data", {}).get("outputs", {})
            print(f"[OK] Dify 调用成功: workflow_run_id={run_id}, status={status}")
            print(f"[INFO] outputs={json.dumps(outputs, ensure_ascii=False)}")
            return 0
        except Exception as e:
            print(f"[WARN] 触发失败: {e}")
            if attempt >= max_retries:
                print("[ERROR] Dify 工作流触发失败，重试耗尽。")
                return 2
            sleep_sec = retry_backoff * attempt
            time.sleep(sleep_sec)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
