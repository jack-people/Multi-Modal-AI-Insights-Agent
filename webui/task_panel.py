import json
import streamlit as st


def render_mvp_overview_sidebar() -> None:
    st.divider()
    st.subheader("🎬 MVP 演示总览")
    task_runtime = st.session_state.get("task_runtime", {})
    pending_action_count = len(st.session_state.get("action_pending_queue", []))
    step_status = task_runtime.get("step_status", "unknown")
    critic_decision = task_runtime.get("critic_decision", "-")
    critic_score = task_runtime.get("critic_score", "-")
    evidence_total = int(task_runtime.get("evidence_total", 0) or 0)
    evidence_matched = int(task_runtime.get("evidence_matched", 0) or 0)
    evidence_coverage = float(task_runtime.get("evidence_coverage", 0.0) or 0.0)
    st.caption(
        f"步骤状态: {step_status} | 审查决策: {critic_decision} | 审查评分: {critic_score}"
    )
    st.caption(
        f"证据覆盖: {evidence_matched}/{evidence_total} ({evidence_coverage:.2f}) | 待确认动作: {pending_action_count}"
    )
    if task_runtime.get("critic_feedback"):
        st.caption(f"审查反馈: {task_runtime.get('critic_feedback')}")
    with st.expander("证据与审查详情"):
        st.caption(f"cited_ids: {task_runtime.get('evidence_cited_ids', [])}")
        st.caption(f"matched_ids: {task_runtime.get('evidence_matched_ids', [])}")
        evidence_items = task_runtime.get("evidence_items", []) or []
        if evidence_items:
            for item in evidence_items:
                st.write(
                    f"- [{item.get('id', '-')}] source={item.get('source', '-')}"
                    f" | query={item.get('query', '-')}"
                )
                if item.get("snippet"):
                    st.caption(str(item["snippet"]))
        else:
            st.caption("暂无证据明细")


def render_task_board_sidebar(session_id: str) -> None:
    st.divider()
    st.subheader("🗂️ 任务执行看板")
    task_runtime = st.session_state.get("task_runtime", {})
    task_plan = task_runtime.get("task_plan", [])
    if task_runtime.get("task_plan_summary"):
        st.caption(task_runtime["task_plan_summary"])

    if task_plan:
        current_step = int(task_runtime.get("current_step", 0))
        step_status = task_runtime.get("step_status", "unknown")
        st.caption(f"当前步骤: {current_step + 1}/{len(task_plan)}")
        st.caption(f"步骤状态: {step_status}")
        if task_runtime.get("last_failure_summary"):
            st.warning(f"最近失败原因: {task_runtime['last_failure_summary']}")
        for i, step in enumerate(task_plan, 1):
            prefix = "👉 " if i - 1 == current_step else "• "
            st.write(f"{prefix}{i}. {step}")

        st.caption("步骤时间线")
        for row in task_runtime.get("step_timeline", []):
            start_text = row["start_at"] or "-"
            end_text = row["end_at"] or "-"
            st.write(
                f"{row['step_index'] + 1}. [{row['status']}] "
                f"{row['step_name']} ({start_text} -> {end_text})"
            )
            if row.get("fail_reason"):
                st.caption(f"原因: {row['fail_reason']}")

        st.download_button(
            "导出任务运行JSON",
            data=json.dumps(task_runtime, ensure_ascii=False, indent=2),
            file_name=f"task_runtime_{session_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.caption("暂无任务计划")
