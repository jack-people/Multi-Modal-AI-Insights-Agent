import unittest

from node.common import (
    parse_tool_message,
    collect_evidence,
    collect_vision_evidence,
    collect_action_evidence,
    extract_cited_evidence_ids,
)
from web_task_runtime import update_task_runtime_from_node


class _Msg:
    def __init__(self, content: str):
        self.content = content


class RuntimeHelperTests(unittest.TestCase):
    def test_parse_tool_message_ok(self):
        raw = '{"ok":true,"source":"web_news","query":"q","data":"hello","error":""}'
        self.assertEqual(parse_tool_message(raw), "[web_news] hello")

    def test_parse_tool_message_error(self):
        raw = '{"ok":false,"source":"dify_arxiv_db","query":"q","data":"","error":"boom"}'
        self.assertEqual(parse_tool_message(raw), "[dify_arxiv_db][ERROR] boom")

    def test_collect_evidence_from_tool_messages(self):
        tool_msg = _Msg('{"ok":true,"source":"web_news","query":"edge ai","data":"news body","error":""}')
        tool_msg.type = "tool"
        evidence = collect_evidence([tool_msg])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["id"], "E1")
        self.assertEqual(evidence[0]["source"], "web_news")

    def test_extract_cited_evidence_ids(self):
        cited = extract_cited_evidence_ids("结论如下 [E1]，视觉依据 [V1]，动作依据 [A1]，另外参考 [E3]。")
        self.assertEqual(cited, {"E1", "E3", "V1", "A1"})

    def test_collect_vision_evidence(self):
        state = {
            "vision_mode": "chart",
            "vision_image_name": "figure1.png",
            "vision_context": "图中展示模型A优于模型B。",
            "vision_ocr_text": "A 0.92, B 0.88",
            "vision_key_points": ["A领先B", "差距约4%"],
            "vision_chart_insights": ["趋势稳定上升"],
            "vision_uncertainties": ["坐标轴单位不清晰"],
        }
        evidence = collect_vision_evidence(state)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["id"], "V1")
        self.assertEqual(evidence[0]["source"], "vision")
        self.assertIn("mode=chart", evidence[0]["query"])

    def test_collect_action_evidence(self):
        state = {
            "action_results": [
                {
                    "action": "action_write_report_file",
                    "status": "executed",
                    "message": "文件写入成功: action_outputs/report.md",
                    "output_path": "action_outputs/report.md",
                }
            ]
        }
        evidence = collect_action_evidence(state)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["id"], "A1")
        self.assertEqual(evidence[0]["source"], "action")
        self.assertIn("executed", evidence[0]["snippet"])

    def test_update_task_runtime_on_retry(self):
        runtime = {
            "task_plan": ["step1", "step2"],
            "current_step": 0,
            "step_status": "needs_retry",
            "step_timeline": [],
            "last_failure_summary": "",
        }
        node_state = {
            "step_status": "needs_retry",
            "messages": [_Msg("【Critic 审查未通过】由于以下原因，你的上一轮工作不及格：\n关键词太窄\n请立刻根据建议更换搜索策略重新查询！")],
        }
        update_task_runtime_from_node("critic", node_state, runtime)

        self.assertEqual(runtime["step_timeline"][0]["status"], "needs_retry")
        self.assertIn("关键词太窄", runtime["last_failure_summary"])

    def test_update_task_runtime_on_completed(self):
        runtime = {
            "task_plan": ["step1"],
            "current_step": 0,
            "step_status": "completed",
            "step_timeline": [],
            "last_failure_summary": "",
        }
        node_state = {
            "step_status": "completed",
            "critic_decision": "ACCEPT",
            "critic_score": 9,
            "evidence_total": 3,
            "evidence_matched": 2,
            "evidence_coverage": 0.66,
        }
        update_task_runtime_from_node("critic", node_state, runtime)
        self.assertEqual(runtime["step_timeline"][0]["status"], "completed")
        self.assertTrue(runtime["step_timeline"][0]["end_at"])
        self.assertEqual(runtime["critic_score"], 9)
        self.assertEqual(runtime["evidence_total"], 3)

    def test_update_task_runtime_in_progress_marks_previous_step(self):
        runtime = {
            "task_plan": ["step1", "step2"],
            "current_step": 1,
            "step_status": "in_progress",
            "step_timeline": [],
            "last_failure_summary": "",
        }
        node_state = {"step_status": "in_progress", "current_step": 1}
        update_task_runtime_from_node("critic", node_state, runtime)
        self.assertEqual(runtime["step_timeline"][0]["status"], "completed")
        self.assertEqual(runtime["step_timeline"][1]["status"], "in_progress")

    def test_update_task_runtime_invalid_status_falls_back_unknown(self):
        runtime = {
            "task_plan": ["step1"],
            "current_step": 0,
            "step_status": "oops",
            "step_timeline": [],
        }
        node_state = {"step_status": "oops"}
        update_task_runtime_from_node("executor", node_state, runtime)
        self.assertEqual(runtime["step_status"], "unknown")
        self.assertEqual(runtime["step_timeline"][0]["status"], "unknown")

    def test_update_task_runtime_copies_evidence_fields(self):
        runtime = {"task_plan": ["step1"], "step_timeline": []}
        node_state = {
            "step_status": "completed",
            "evidence_items": [{"id": "E1"}],
            "evidence_cited_ids": ["E1"],
            "evidence_matched_ids": ["E1"],
        }
        update_task_runtime_from_node("critic", node_state, runtime)
        self.assertEqual(runtime["evidence_items"][0]["id"], "E1")
        self.assertEqual(runtime["evidence_cited_ids"], ["E1"])
        self.assertEqual(runtime["evidence_matched_ids"], ["E1"])


if __name__ == "__main__":
    unittest.main()
