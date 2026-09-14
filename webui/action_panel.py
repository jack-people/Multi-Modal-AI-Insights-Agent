import streamlit as st


def render_action_sidebar_sections(
    action_audit_log_path: str,
    load_audit_rows_func,
    execute_confirmed_action_func,
    append_audit_log_func,
    record_action_outcome_func,
    drop_pending_action_func,
) -> None:
    st.divider()
    st.subheader("🛡️ 动作确认队列")
    pending_actions = st.session_state.action_pending_queue
    if pending_actions:
        for item in list(pending_actions):
            st.caption(
                f"{item.get('action', '-')}"
                f" | risk={item.get('risk', '-')}"
                f" | status={item.get('status', '-')}"
            )
            if item.get("message"):
                st.write(item["message"])

            col1, col2 = st.columns(2)
            with col1:
                if st.button("确认执行", key=f"confirm_{item['id']}", use_container_width=True):
                    result = execute_confirmed_action_func(item.get("action", ""), item.get("confirm_payload", {}))
                    audit_status = "executed" if result.get("ok", False) else "failed"
                    detail = result.get("message", "")
                    append_audit_log_func(
                        item.get("action", ""),
                        item.get("risk", "high"),
                        audit_status,
                        detail,
                        meta={"query": item.get("query", ""), "confirmed_in_web": True},
                    )
                    record_action_outcome_func(
                        action=item.get("action", ""),
                        status=audit_status,
                        message=detail,
                        output_path=result.get("output_path", ""),
                        command_output=result.get("command_output", ""),
                    )
                    st.session_state.pending_action_prompt = "请基于最新动作执行结果继续完成任务，并明确下一步建议。"
                    drop_pending_action_func(item["id"])
                    st.rerun()
            with col2:
                if st.button("拒绝执行", key=f"reject_{item['id']}", use_container_width=True):
                    append_audit_log_func(
                        item.get("action", ""),
                        item.get("risk", "high"),
                        "rejected",
                        "用户在Web端拒绝执行该动作。",
                        meta={"query": item.get("query", ""), "confirmed_in_web": False},
                    )
                    record_action_outcome_func(
                        action=item.get("action", ""),
                        status="rejected",
                        message="用户拒绝执行",
                    )
                    st.session_state.pending_action_prompt = "动作被用户拒绝，请基于当前信息给出替代执行方案。"
                    drop_pending_action_func(item["id"])
                    st.rerun()
    else:
        st.caption("暂无待确认动作")

    if st.session_state.action_execution_logs:
        st.caption("最近动作结果")
        for row in st.session_state.action_execution_logs[-5:]:
            st.write(f"- [{row['status']}] {row['action']}: {row['message']}")

    st.divider()
    st.subheader("📜 动作审计日志")
    audit_status_filter = st.selectbox(
        "状态筛选",
        options=["all", "executed", "pending_confirmation", "rejected", "failed"],
        index=0,
        key="audit_status_filter",
    )
    audit_limit = st.slider(
        "显示最近条数",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
        key="audit_limit",
    )
    audit_rows = load_audit_rows_func(limit=audit_limit, status_filter=audit_status_filter)
    st.caption(f"log_path: {action_audit_log_path}")
    if audit_rows:
        for row in audit_rows:
            st.write(
                f"- [{row.get('status', '-')}] {row.get('action', '-')}"
                f" @ {row.get('ts', '-')}"
            )
            if row.get("detail"):
                st.caption(str(row["detail"]))
    else:
        st.caption("暂无可显示的审计日志")

    st.divider()
    st.subheader("🔁 最近回写动作上下文")
    latest_action_context = st.session_state.get("latest_action_context", [])
    if latest_action_context:
        st.caption("以下内容已作为 action_results 回写给 Agent，可在回答中用 [A#] 引用。")
        for idx, item in enumerate(latest_action_context, 1):
            st.write(
                f"- [A{idx}] {item.get('action', '-')}"
                f" | status={item.get('status', '-')}"
                f" | message={item.get('message', '-')}"
            )
            if item.get("output_path"):
                st.caption(f"output_path: {item['output_path']}")
            if item.get("command_output"):
                st.code(str(item["command_output"]))
    else:
        st.caption("暂无已回写动作上下文")
