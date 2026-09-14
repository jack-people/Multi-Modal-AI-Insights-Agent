import streamlit as st


def render_profile_sidebar(load_thread_memory_func, save_user_profile_func) -> str:
    st.header("⚙️ 会话设置")
    session_id = st.text_input("当前会话 ID (Thread ID)", value="session-web-001")
    st.caption("💡 提示：更改会话 ID 即可开启全新的无记忆对话；随时换回旧 ID，即可恢复历史长期记忆！")

    if st.session_state.profile_loaded_thread != session_id:
        bundle = load_thread_memory_func(session_id)
        loaded_profile = bundle.get("profile", {})
        loaded_notes = bundle.get("memory_notes", [])
        st.session_state.current_user_profile = loaded_profile
        st.session_state.current_memory_notes = loaded_notes
        st.session_state.pref_answer_style = loaded_profile.get("answer_style", "balanced")
        st.session_state.pref_tone = loaded_profile.get("tone", "professional")
        st.session_state.pref_use_structure = bool(loaded_profile.get("use_structure", True))
        st.session_state.profile_loaded_thread = session_id

    st.divider()
    st.subheader("🧠 个性化偏好")
    st.selectbox(
        "回答风格",
        options=["concise", "balanced", "detailed"],
        key="pref_answer_style",
        help="concise=简洁，balanced=均衡，detailed=详细",
    )
    st.selectbox(
        "语气",
        options=["professional", "casual"],
        key="pref_tone",
    )
    st.toggle(
        "偏好结构化输出",
        key="pref_use_structure",
        help="开启后更偏好分点、分段展示。",
    )
    if st.button("保存偏好", use_container_width=True):
        saved = save_user_profile_func(
            session_id,
            {
                "answer_style": st.session_state.pref_answer_style,
                "tone": st.session_state.pref_tone,
                "use_structure": bool(st.session_state.pref_use_structure),
            },
        )
        st.session_state.current_user_profile = saved
        st.success("偏好已保存。")
    st.caption(f"当前偏好: {st.session_state.current_user_profile}")

    st.caption("长期记忆（高价值）")
    if st.session_state.current_memory_notes:
        for i, note in enumerate(st.session_state.current_memory_notes[-5:], 1):
            st.write(f"- M{i}: {note}")
    else:
        st.caption("暂无长期记忆")
    if st.session_state.last_relevant_memory_notes:
        st.caption("最近一次召回的相关长期记忆")
        for i, note in enumerate(st.session_state.last_relevant_memory_notes, 1):
            st.write(f"- R{i}: {note}")

    st.caption("短期记忆（会话内）")
    short_term_messages = [
        m for m in st.session_state.get("messages", []) if m.get("role") in {"user", "assistant"}
    ]
    if short_term_messages:
        st.caption(f"当前会话消息数: {len(short_term_messages)}")
    else:
        st.caption("当前会话暂无短期记忆")

    return session_id
