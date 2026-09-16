import json
import os
from datetime import datetime
from typing import Any

from harness.checks.common import evaluate_case
from harness.core.workspace import HarnessWorkspace


def _pick_runner(entry: str, api_base_url: str):
    if entry == "api":
        from harness.runners.api_runner import ApiRunner
        return ApiRunner(api_base_url)
    if entry == "mcp":
        from harness.runners.mcp_runner import McpRunner
        return McpRunner()
    from harness.runners.local_runner import LocalRunner
    return LocalRunner()


def _resolve_templates(case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(case, ensure_ascii=False)
    for key, value in context.items():
        raw = raw.replace("{{" + key + "}}", str(value))
    return json.loads(raw)


def _extract_context(result_payload: dict[str, Any], context: dict[str, Any]) -> None:
    if not isinstance(result_payload, dict):
        return
    if "action_id" in result_payload and result_payload.get("action_id"):
        context["last_action_id"] = result_payload["action_id"]
    queue = result_payload.get("action_pending_queue", [])
    if isinstance(queue, list) and queue:
        first = queue[0]
        if isinstance(first, dict) and first.get("id"):
            context["last_action_id"] = first["id"]
    if result_payload.get("answer"):
        context["last_answer"] = str(result_payload.get("answer", ""))


def _to_markdown(report: dict[str, Any]) -> str:
    total = report["summary"]["total"]
    passed = report["summary"]["passed"]
    failed = report["summary"]["failed"]
    pass_rate = report["summary"]["pass_rate"]
    lines = [
        "# Harness Report",
        "",
        f"- time: {report['summary']['ts']}",
        f"- total: {total}",
        f"- passed: {passed}",
        f"- failed: {failed}",
        f"- pass_rate: {pass_rate:.1f}%",
        "",
        "## Case Results",
    ]
    for row in report["results"]:
        mark = "PASS" if row["passed"] else "FAIL"
        lines.append(f"- [{mark}] `{row['id']}` ({row['entry']}/{row['action']}) latency={row['latency_ms']}ms")
        for fmsg in row["failures"]:
            lines.append(f"  - {fmsg}")
    return "\n".join(lines) + "\n"


def execute_run(ws: HarnessWorkspace, write_latest_report_dir: str | None = None) -> dict[str, Any]:
    manifest = ws.read_json("manifest.json")
    plan = ws.read_json("plan.json")
    context = ws.read_json("context.json", default={})
    api_base_url = manifest.get("api_base_url", "http://127.0.0.1:8001")
    ws.mark_state("running")

    results = ws.read_jsonl("results.jsonl")
    results_by_id = {str(x.get("id", "")): x for x in results if isinstance(x, dict)}
    runners: dict[str, Any] = {}
    done_ids = {x.get("id") for x in ws.read_json("progress.json", default={"done_cases": []}).get("done_cases", [])}

    for raw_case in plan.get("cases", []):
        case = _resolve_templates(raw_case, context)
        case_id = case.get("id")
        if case_id in done_ids:
            continue
        entry = str(case.get("entry", "local"))
        ws.append_jsonl("events.jsonl", {"ts": datetime.now().isoformat(), "event": "case_started", "case_id": case_id})
        runner = runners.get(entry)
        if runner is None:
            try:
                runner = _pick_runner(entry, api_base_url)
                runners[entry] = runner
            except Exception as e:
                row = {
                    "id": case_id,
                    "entry": entry,
                    "action": case.get("action"),
                    "latency_ms": 0,
                    "status_code": 500,
                    "passed": False,
                    "failures": [f"runner init failed: {e}"],
                    "payload": {"ok": False, "error": str(e)},
                }
                results_by_id[str(case_id)] = row
                ws.append_jsonl("results.jsonl", row)
                ws.append_jsonl("events.jsonl", {"ts": datetime.now().isoformat(), "event": "case_finished", "case_id": case_id, "passed": False})
                continue

        try:
            run_result = runner.run_case(case, context)
        except Exception as e:
            run_result = {
                "ok": False,
                "status_code": 500,
                "latency_ms": 0,
                "payload": {"ok": False, "error": str(e)},
            }
        payload = run_result.get("payload", {})
        _extract_context(payload if isinstance(payload, dict) else {}, context)
        failures = evaluate_case(case, run_result)
        row = {
            "id": case_id,
            "entry": entry,
            "action": case.get("action"),
            "latency_ms": run_result.get("latency_ms", 0),
            "status_code": run_result.get("status_code"),
            "passed": len(failures) == 0,
            "failures": failures,
            "payload": payload,
        }
        results_by_id[str(case_id)] = row
        ws.append_jsonl("results.jsonl", row)
        ws.append_jsonl("events.jsonl", {"ts": datetime.now().isoformat(), "event": "case_finished", "case_id": case_id, "passed": row["passed"]})
        done_ids.add(case_id)
        ws.write_json("context.json", context)
        ws.write_json("progress.json", {"done_cases": [{"id": x} for x in sorted(done_ids)]})

    all_case_ids = [str(x.get("id", "")) for x in plan.get("cases", [])]
    merged_results = [results_by_id[cid] for cid in all_case_ids if cid in results_by_id]
    total = len(merged_results)
    passed = sum(1 for x in merged_results if x["passed"])
    failed = total - passed
    report = {
        "suite": plan.get("suite", ""),
        "summary": {
            "ts": datetime.now().isoformat(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed * 100.0 / total) if total else 0.0,
        },
        "results": merged_results,
    }
    ws.write_json("report.json", report)
    report_md = _to_markdown(report)
    ws.write_text("report.md", report_md)
    ws.mark_state("finished" if failed == 0 else "failed", extra={"failed": failed, "passed": passed})

    if write_latest_report_dir:
        os.makedirs(write_latest_report_dir, exist_ok=True)
        with open(os.path.join(write_latest_report_dir, "latest.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(os.path.join(write_latest_report_dir, "latest.md"), "w", encoding="utf-8") as f:
            f.write(report_md)

    return report
