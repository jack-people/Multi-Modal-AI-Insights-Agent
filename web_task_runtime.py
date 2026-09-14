from datetime import datetime

VALID_STEP_STATUS = {"planned", "in_progress", "awaiting_review", "needs_retry", "completed", "pending", "unknown"}


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def extract_critic_feedback(node_state: dict) -> str:
    messages = node_state.get("messages", []) if isinstance(node_state, dict) else []
    if not messages:
        return ""

    last_msg = messages[-1]
    content = getattr(last_msg, "content", "") or ""
    if "【Critic 审查未通过】" not in content:
        return ""

    parts = content.split("由于以下原因，你的上一轮工作不及格：")
    if len(parts) < 2:
        return content.strip()
    return parts[1].replace("请立刻根据建议更换搜索策略重新查询！", "").strip()


def ensure_timeline(task_runtime: dict) -> None:
    task_plan = task_runtime.get("task_plan", [])
    timeline = task_runtime.setdefault("step_timeline", [])
    while len(timeline) < len(task_plan):
        idx = len(timeline)
        timeline.append(
            {
                "step_index": idx,
                "step_name": task_plan[idx],
                "start_at": "",
                "end_at": "",
                "status": "pending",
                "fail_reason": "",
            }
        )


def update_task_runtime_from_node(node_name: str, node_state: dict, task_runtime: dict) -> None:
    for key in (
        "task_plan",
        "task_plan_summary",
        "current_step",
        "step_status",
        "critic_decision",
        "critic_score",
        "critic_feedback",
        "evidence_total",
        "evidence_matched",
        "evidence_coverage",
        "evidence_items",
        "evidence_cited_ids",
        "evidence_matched_ids",
    ):
        if key in node_state:
            task_runtime[key] = node_state[key]

    ensure_timeline(task_runtime)
    timeline = task_runtime.get("step_timeline", [])
    if not timeline:
        return

    current_step = int(task_runtime.get("current_step", 0))
    step_status = task_runtime.get("step_status", "unknown")
    if step_status not in VALID_STEP_STATUS:
        step_status = "unknown"
        task_runtime["step_status"] = "unknown"
    current_step = max(0, min(current_step, len(timeline) - 1))
    task_runtime["current_step"] = current_step

    if node_name == "executor":
        entry = timeline[current_step]
        if not entry["start_at"]:
            entry["start_at"] = now_ts()
        entry["status"] = step_status

    if node_name == "critic":
        if step_status == "needs_retry":
            entry = timeline[current_step]
            if not entry["start_at"]:
                entry["start_at"] = now_ts()
            entry["status"] = "needs_retry"
            feedback = extract_critic_feedback(node_state)
            if feedback:
                entry["fail_reason"] = feedback
                task_runtime["last_failure_summary"] = feedback

        elif step_status == "completed":
            entry = timeline[current_step]
            if not entry["start_at"]:
                entry["start_at"] = now_ts()
            entry["status"] = "completed"
            if not entry["end_at"]:
                entry["end_at"] = now_ts()

        elif step_status == "in_progress":
            prev_step = current_step - 1
            if prev_step >= 0:
                prev_entry = timeline[prev_step]
                if not prev_entry["start_at"]:
                    prev_entry["start_at"] = now_ts()
                prev_entry["status"] = "completed"
                if not prev_entry["end_at"]:
                    prev_entry["end_at"] = now_ts()

            next_entry = timeline[current_step]
            if not next_entry["start_at"]:
                next_entry["start_at"] = now_ts()
            next_entry["status"] = "in_progress"
