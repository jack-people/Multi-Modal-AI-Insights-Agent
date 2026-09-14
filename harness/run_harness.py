import argparse
import json
from harness.core.executor import execute_run
from harness.core.initializer import initialize_run
from harness.core.workspace import HarnessWorkspace


def main():
    parser = argparse.ArgumentParser(description="Project Harness Runner (Initializer + Executor)")
    parser.add_argument(
        "--suite",
        default="harness/cases/core_10_cases.json",
        help="case suite json file path",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8001",
        help="api base url for api entry cases",
    )
    parser.add_argument(
        "--report-dir",
        default="harness/report",
        help="output report directory",
    )
    parser.add_argument(
        "--workspace-root",
        default="harness/workspace",
        help="workspace root directory",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="resume by run_id (if provided, skip initialize)",
    )
    args = parser.parse_args()

    if args.run_id:
        ws = HarnessWorkspace.open(args.workspace_root, args.run_id)
    else:
        ws = initialize_run(
            suite_path=args.suite,
            api_base_url=args.api_base_url,
            report_dir=args.report_dir,
            workspace_root=args.workspace_root,
            run_id=None,
        )
    report = execute_run(ws, write_latest_report_dir=args.report_dir)

    print(json.dumps(report["summary"], ensure_ascii=False))
    if int(report["summary"].get("failed", 0)) > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
