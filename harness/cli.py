import argparse
import json

from harness.core.executor import execute_run
from harness.core.initializer import initialize_run
from harness.core.workspace import HarnessWorkspace


def _print_exec_and_exit(ws: HarnessWorkspace, report_dir: str) -> None:
    report = execute_run(ws, write_latest_report_dir=report_dir)
    print(json.dumps({"run_id": ws.run_id, **report["summary"]}, ensure_ascii=False))
    raise SystemExit(1 if int(report["summary"].get("failed", 0)) > 0 else 0)


def main():
    parser = argparse.ArgumentParser(description="Harness CLI (Initializer + Executor + Workspace)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="initialize run plan into workspace")
    p_init.add_argument("--suite", required=True)
    p_init.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    p_init.add_argument("--report-dir", default="harness/report")
    p_init.add_argument("--workspace-root", default="harness/workspace")
    p_init.add_argument("--run-id", default="")

    p_exec = sub.add_parser("exec", help="execute existing run_id")
    p_exec.add_argument("--run-id", required=True)
    p_exec.add_argument("--workspace-root", default="harness/workspace")
    p_exec.add_argument("--report-dir", default="harness/report")

    p_run = sub.add_parser("run", help="init then execute")
    p_run.add_argument("--suite", required=True)
    p_run.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    p_run.add_argument("--report-dir", default="harness/report")
    p_run.add_argument("--workspace-root", default="harness/workspace")
    p_run.add_argument("--run-id", default="")

    p_resume = sub.add_parser("resume", help="resume existing run")
    p_resume.add_argument("--run-id", required=True)
    p_resume.add_argument("--workspace-root", default="harness/workspace")
    p_resume.add_argument("--report-dir", default="harness/report")

    args = parser.parse_args()

    if args.cmd == "init":
        ws = initialize_run(
            suite_path=args.suite,
            api_base_url=args.api_base_url,
            report_dir=args.report_dir,
            workspace_root=args.workspace_root,
            run_id=args.run_id or None,
        )
        print(json.dumps({"ok": True, "run_id": ws.run_id}, ensure_ascii=False))
        return

    if args.cmd == "exec":
        ws = HarnessWorkspace.open(args.workspace_root, args.run_id)
        _print_exec_and_exit(ws, args.report_dir)

    if args.cmd == "run":
        ws = initialize_run(
            suite_path=args.suite,
            api_base_url=args.api_base_url,
            report_dir=args.report_dir,
            workspace_root=args.workspace_root,
            run_id=args.run_id or None,
        )
        _print_exec_and_exit(ws, args.report_dir)

    ws = HarnessWorkspace.open(args.workspace_root, args.run_id)
    _print_exec_and_exit(ws, args.report_dir)


if __name__ == "__main__":
    main()
