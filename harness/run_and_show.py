import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run/Resume harness then print markdown report")
    parser.add_argument("--mode", choices=["run", "exec", "resume"], default="run")
    parser.add_argument("--suite", default="harness/cases/ci_gate.json")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--report-dir", default="harness/report")
    parser.add_argument("--workspace-root", default="harness/workspace")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--json-only", action="store_true", help="only print final json summary for CI")
    args = parser.parse_args()

    cmd = [sys.executable, "-m", "harness.cli", args.mode]
    if args.mode == "run":
        cmd += [
            "--suite",
            args.suite,
            "--api-base-url",
            args.api_base_url,
            "--report-dir",
            args.report_dir,
            "--workspace-root",
            args.workspace_root,
        ]
        if args.run_id:
            cmd += ["--run-id", args.run_id]
    else:
        if not args.run_id:
            raise SystemExit("--mode exec/resume 时必须提供 --run-id")
        cmd += [
            "--run-id",
            args.run_id,
            "--report-dir",
            args.report_dir,
            "--workspace-root",
            args.workspace_root,
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr and not args.json_only:
        print(proc.stderr.strip())

    resolved_run_id = args.run_id
    if not resolved_run_id and proc.stdout:
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            resolved_run_id = str(payload.get("run_id", "")).strip()
        except Exception:
            resolved_run_id = ""

    if args.json_only:
        summary = {"ok": proc.returncode == 0, "run_id": resolved_run_id}
        if proc.stdout:
            try:
                payload = json.loads(proc.stdout.strip().splitlines()[-1])
                if isinstance(payload, dict):
                    summary.update(payload)
            except Exception:
                pass
        print(json.dumps(summary, ensure_ascii=False))
        raise SystemExit(proc.returncode)

    md_path = Path(args.report_dir) / "latest.md"
    if md_path.exists():
        print("\n===== harness/report/latest.md =====\n")
        print(md_path.read_text(encoding="utf-8"))
    else:
        print("\n[warn] latest.md not found")

    if resolved_run_id:
        ws_md = Path(args.workspace_root) / resolved_run_id / "report.md"
        if ws_md.exists():
            print(f"\n===== workspace report ({resolved_run_id}) =====\n")
            print(ws_md.read_text(encoding="utf-8"))

    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
