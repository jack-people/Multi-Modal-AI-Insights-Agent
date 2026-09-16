import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.multiModal_agent.schemas import AnalysisReport
from mcp_tools.paper_jobs import paper_run_start, paper_run_status, reset_jobs_for_tests


class _FakeAgent:
    def run(self, paper_limit: int, news_limit: int, top_k: int):
        report = AnalysisReport.empty()
        report.model_status = "ok"
        report.executive_summary = f"fake paper_limit={paper_limit} top_k={top_k}"
        return report


class PaperJobTests(unittest.TestCase):
    def setUp(self):
        reset_jobs_for_tests()

    def test_start_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "report.json"
            with (
                patch("agent.multiModal_agent.MultiModalAnalysisAgent", _FakeAgent),
                patch("agent.multiModal_agent.run._build_timestamped_output_path", return_value=report_path),
            ):
                started = paper_run_start(paper_limit=1, top_k=1, news_limit=0)
                self.assertTrue(started["ok"])
                job_id = started["job_id"]
                row = None
                for _ in range(40):
                    row = paper_run_status(job_id)
                    if row.get("status") in {"done", "error"}:
                        break
                    time.sleep(0.05)
                self.assertIsNotNone(row)
                self.assertEqual(row.get("status"), "done", row)
                self.assertEqual(row.get("report_path"), str(report_path))
                self.assertTrue(report_path.exists())

    def test_unknown_job(self):
        result = paper_run_status("missing")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "MM404_JOB_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
