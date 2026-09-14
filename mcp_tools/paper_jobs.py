from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_job(job_id: str, **updates: Any) -> dict[str, Any]:
    with _lock:
        row = dict(_jobs.get(job_id, {"job_id": job_id}))
        row.update(updates)
        _jobs[job_id] = row
        return dict(row)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _jobs.get(job_id)
        return dict(row) if row else None


def _run_job(job_id: str, paper_limit: int, top_k: int, news_limit: int) -> None:
    _set_job(job_id, status="running", updated_at=_now_iso())
    try:
        from agent.multiModal_agent import MultiModalAnalysisAgent
        from agent.multiModal_agent.run import _build_timestamped_output_path

        agent = MultiModalAnalysisAgent()
        report = agent.run(paper_limit=paper_limit, news_limit=news_limit, top_k=top_k)
        out_path = _build_timestamped_output_path("output/multiModal_agent")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        _set_job(
            job_id,
            status="done",
            report_path=str(out_path),
            model_status=getattr(report, "model_status", ""),
            error="",
            updated_at=_now_iso(),
        )
    except Exception as exc:
        _set_job(
            job_id,
            status="error",
            error=str(exc),
            updated_at=_now_iso(),
        )


def paper_run_start(paper_limit: int = 10, top_k: int = 10, news_limit: int = 0) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    _set_job(
        job_id,
        status="queued",
        paper_limit=int(paper_limit),
        top_k=int(top_k),
        news_limit=int(news_limit),
        report_path="",
        error="",
        model_status="",
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    worker = threading.Thread(
        target=_run_job,
        args=(job_id, int(paper_limit), int(top_k), int(news_limit)),
        daemon=True,
        name=f"paper-job-{job_id}",
    )
    worker.start()
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "message": "论文分析已启动，请用 paper_run_status 轮询。",
    }


def paper_run_status(job_id: str) -> dict[str, Any]:
    row = get_job(str(job_id or "").strip())
    if not row:
        return {
            "ok": False,
            "error_code": "MM404_JOB_NOT_FOUND",
            "message": "job_id 不存在",
            "detail": {"job_id": job_id},
        }
    return {"ok": True, **row}


def reset_jobs_for_tests() -> None:
    with _lock:
        _jobs.clear()
