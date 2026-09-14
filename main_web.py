# 这个文件是程序的主入口，负责启动 Streamlit Web UI，并将编译好的 Agent 图连接到前端界面。
#终端输入：streamlit run main.py来启动
import streamlit as st
import json
import os
import hashlib
from collections import deque
from langchain_core.messages import HumanMessage

# 👉 这里导入你编译好的 Agent 图。
# 如果你的代码拆分了，就是 from graph import app as agent_app
# 如果你的代码还在一个文件里，就把 langgraph_agent_stream 换成你的文件名
from graph import create_agent_app
from config import (
    validate_config,
    VOICE_ENABLED,
    VOICE_AUTO_TTS_DEFAULT,
    VISION_ENABLED,
    VISION_AUTO_ANALYZE_DEFAULT,
    ACTION_AUDIT_LOG_PATH,
)
from runtime_context import set_thread_id, log_event
from web_task_runtime import update_task_runtime_from_node
from voice import transcribe_audio_bytes, synthesize_speech
from vision import analyze_image_bytes
from actions import execute_confirmed_action, append_audit_log
from memory import (
    load_thread_memory,
    save_user_profile,
    append_memory_note,
    infer_profile_updates,
    extract_high_value_memory,
    select_relevant_memory_notes,
)
from webui.action_panel import render_action_sidebar_sections
from webui.vision_panel import render_sidebar_vision_result, render_vision_input_section
from webui.profile_panel import render_profile_sidebar
from webui.task_panel import render_mvp_overview_sidebar, render_task_board_sidebar


@st.cache_resource
def get_agent_app():
    validate_config()
    return create_agent_app()


agent_app = get_agent_app()


def _ensure_session_defaults() -> None:
    defaults = {
        "messages": [],
        "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
        "pending_voice_prompt": "",
        "voice_auto_tts": VOICE_AUTO_TTS_DEFAULT,
        "pending_tts_text": "",
        "last_tts_error": "",
        "vision_auto_analyze": VISION_AUTO_ANALYZE_DEFAULT,
        "pending_vision_context": "",
        "pending_vision_image_name": "",
        "pending_vision_mode": "general",
        "pending_vision_ocr_text": "",
        "pending_vision_key_points": [],
        "pending_vision_chart_insights": [],
        "pending_vision_uncertainties": [],
        "latest_vision_result": {},
        "last_vision_token": "",
        "action_pending_queue": [],
        "action_execution_logs": [],
        "pending_action_results": [],
        "pending_action_prompt": "",
        "latest_action_context": [],
        "last_relevant_memory_notes": [],
        "profile_loaded_thread": "",
        "current_user_profile": {},
        "current_memory_notes": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _parse_action_tool_payload(raw_tool_content: str) -> dict | None:
    try:
        payload = json.loads(raw_tool_content)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    source = str(payload.get("source", "")).strip()
    if not source.startswith("action_"):
        return None

    data_raw = payload.get("data", "")
    data_obj = {}
    if isinstance(data_raw, str):
        try:
            parsed = json.loads(data_raw)
            if isinstance(parsed, dict):
                data_obj = parsed
        except Exception:
            data_obj = {}

    return {
        "source": source,
        "query": str(payload.get("query", "")).strip(),
        "ok": bool(payload.get("ok", False)),
        "error": str(payload.get("error", "")).strip(),
        "data": data_obj,
    }


def _apply_action_updates_from_node_state(node_state: dict) -> None:
    """解析 node_state 中的 tool 消息并更新动作队列/结果缓存。"""
    for msg in node_state.get("messages", []):
        if getattr(msg, "type", "") != "tool":
            continue
        action_payload = _parse_action_tool_payload(getattr(msg, "content", ""))
        if not action_payload:
            continue
        action_data = action_payload.get("data", {})
        status = str(action_data.get("status", "")).strip()
        action_name = action_payload.get("source", "")
        risk = str(action_data.get("risk", "high")).strip() or "high"
        query_text = action_payload.get("query", "")
        message_text = str(action_data.get("message", "")).strip() or action_payload.get("error", "")
        confirm_payload = action_data.get("confirm_payload", {}) or {}

        if status == "pending_confirmation" and bool(action_data.get("requires_confirmation", False)):
            dedupe_key = (
                f"{action_name}|{query_text}|"
                f"{json.dumps(confirm_payload, ensure_ascii=False, sort_keys=True)}"
            )
            exists = any(x.get("dedupe_key") == dedupe_key for x in st.session_state.action_pending_queue)
            if not exists:
                stable_id = hashlib.sha1(dedupe_key.encode("utf-8")).hexdigest()[:12]
                st.session_state.action_pending_queue.append(
                    {
                        "id": f"act_{stable_id}",
                        "dedupe_key": dedupe_key,
                        "action": action_name,
                        "risk": risk,
                        "status": status,
                        "message": message_text,
                        "query": query_text,
                        "confirm_payload": confirm_payload,
                    }
                )
        elif status in {"executed", "failed"}:
            st.session_state.action_execution_logs.append(
                {
                    "action": action_name,
                    "status": status,
                    "message": message_text,
                    "output_path": str(action_data.get("output_path", "")),
                    "command_output": str(action_data.get("command_output", "")),
                }
            )


def _load_audit_rows(limit: int = 20, status_filter: str = "all") -> list[dict]:
    if not os.path.exists(ACTION_AUDIT_LOG_PATH):
        return []
    try:
        with open(ACTION_AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            # 只保留最近窗口，避免日志大时每次全量读入内存
            lines = list(deque(f, maxlen=2000))
    except Exception:
        return []

    rows: list[dict] = []
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        row_status = str(row.get("status", "")).strip()
        if status_filter != "all" and row_status != status_filter:
            continue
        rows.append(row)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def _status_text_for_node(node_name: str) -> tuple[str, str] | None:
    mapping = {
        "intent_router": ("info", "🧭 [Intent Router]: 正在匹配最合适的技能..."),
        "planner": ("info", "🗂️ [Planner]: 正在拆解任务执行步骤..."),
        "executor": ("info", "🔄 [Executor]: 正在执行技能并决定是否调用工具..."),
        "tools": ("info", "🌐 [Tools]: 正在调用工具检索外部资料..."),
        "critic": ("warning", "🕵️ [Critic]: 苛刻的审查员正在评估刚生成的答案..."),
        "synthesizer": ("info", "✍️ [Synthesizer]: DeepSeek-R1 正在进行深度推理撰写解答..."),
    }
    return mapping.get(node_name)


def _auto_learn_user_preferences(session_id: str, prompt: str) -> None:
    auto_updates = infer_profile_updates(prompt)
    if auto_updates:
        current_profile = dict(st.session_state.get("current_user_profile", {}))
        current_profile.update(auto_updates)
        saved_profile = save_user_profile(session_id, current_profile)
        st.session_state.current_user_profile = saved_profile
        st.session_state.pref_answer_style = saved_profile.get("answer_style", "balanced")
        st.session_state.pref_tone = saved_profile.get("tone", "professional")
        st.session_state.pref_use_structure = bool(saved_profile.get("use_structure", True))
        st.caption(f"已自动更新偏好: {auto_updates}")

    high_value_note = extract_high_value_memory(prompt)
    if high_value_note:
        notes = append_memory_note(session_id, high_value_note)
        st.session_state.current_memory_notes = notes
        st.caption(f"已写入长期记忆: {high_value_note}")


def _consume_pending_context() -> dict:
    """消费会话中的待处理上下文，并清空对应 pending 字段。"""
    action_results = st.session_state.pending_action_results
    st.session_state.pending_action_results = []
    st.session_state.pending_action_prompt = ""
    if action_results:
        st.session_state.latest_action_context = list(action_results)

    payload_ctx = {
        "action_results": action_results,
        "vision_context": st.session_state.pending_vision_context,
        "vision_image_name": st.session_state.pending_vision_image_name,
        "vision_mode": st.session_state.pending_vision_mode,
        "vision_ocr_text": st.session_state.pending_vision_ocr_text,
        "vision_key_points": st.session_state.pending_vision_key_points,
        "vision_chart_insights": st.session_state.pending_vision_chart_insights,
        "vision_uncertainties": st.session_state.pending_vision_uncertainties,
    }

    st.session_state.pending_vision_context = ""
    st.session_state.pending_vision_image_name = ""
    st.session_state.pending_vision_mode = "general"
    st.session_state.pending_vision_ocr_text = ""
    st.session_state.pending_vision_key_points = []
    st.session_state.pending_vision_chart_insights = []
    st.session_state.pending_vision_uncertainties = []
    return payload_ctx


def _build_agent_input_payload(prompt: str, relevant_memory_notes: list[str], payload_ctx: dict) -> dict:
    return {
        "messages": [HumanMessage(content=prompt)],
        "vision_context": payload_ctx["vision_context"],
        "vision_image_name": payload_ctx["vision_image_name"],
        "vision_mode": payload_ctx["vision_mode"],
        "vision_ocr_text": payload_ctx["vision_ocr_text"],
        "vision_key_points": payload_ctx["vision_key_points"],
        "vision_chart_insights": payload_ctx["vision_chart_insights"],
        "vision_uncertainties": payload_ctx["vision_uncertainties"],
        "action_results": payload_ctx["action_results"],
        "user_profile": st.session_state.get("current_user_profile", {}),
        "user_memory_notes": relevant_memory_notes,
    }


def _record_action_outcome(
    action: str,
    status: str,
    message: str,
    output_path: str = "",
    command_output: str = "",
) -> None:
    row = {
        "action": action,
        "status": status,
        "message": message,
        "output_path": output_path,
        "command_output": command_output,
    }
    st.session_state.action_execution_logs.append(dict(row))
    st.session_state.pending_action_results.append(dict(row))


def _drop_pending_action(action_id: str) -> None:
    st.session_state.action_pending_queue = [
        x for x in st.session_state.action_pending_queue if x["id"] != action_id
    ]

# 1. 设置网页基础配置
st.set_page_config(page_title="多模态 AI 专家", page_icon="🤖", layout="wide")
st.title("🤖 多模态 AI Agent 检索系统")
_ensure_session_defaults()

# 2. 侧边栏：用于控制会话与长期记忆
with st.sidebar:
    session_id = render_profile_sidebar(
        load_thread_memory_func=load_thread_memory,
        save_user_profile_func=save_user_profile,
    )
    render_mvp_overview_sidebar()
    render_task_board_sidebar(session_id=session_id)

    render_sidebar_vision_result()
    render_action_sidebar_sections(
        action_audit_log_path=ACTION_AUDIT_LOG_PATH,
        load_audit_rows_func=_load_audit_rows,
        execute_confirmed_action_func=execute_confirmed_action,
        append_audit_log_func=append_audit_log,
        record_action_outcome_func=_record_action_outcome,
        drop_pending_action_func=_drop_pending_action,
    )

config = {"configurable": {"thread_id": session_id}}

# 3. 本地 UI 会话状态已由 _ensure_session_defaults() 统一初始化

render_vision_input_section(
    vision_enabled=VISION_ENABLED,
    analyze_image_bytes_func=analyze_image_bytes,
)

# 语音输入区（开启语音能力时显示）
if VOICE_ENABLED:
    st.divider()
    st.subheader("🎙️ 语音输入")
    st.toggle(
        "自动语音播报",
        key="voice_auto_tts",
        help="开启后，Agent 回答完成会自动尝试 TTS 播报。",
    )

    audio_clip = st.audio_input("点击录音后可直接提问")
    if audio_clip is not None:
        if st.button("使用该语音提问", use_container_width=True):
            with st.spinner("正在进行语音识别（ASR）..."):
                asr_result = transcribe_audio_bytes(audio_clip.getvalue(), filename=getattr(audio_clip, "name", "voice.wav"))
            if asr_result["ok"]:
                st.session_state.pending_voice_prompt = asr_result["text"]
                st.success("语音识别成功，已填入本轮提问。")
                st.caption(f"识别文本：{asr_result['text']}")
            else:
                st.error(f"语音识别失败：{asr_result['error']}")

    if st.session_state.pending_tts_text:
        if st.session_state.last_tts_error:
            st.warning(f"上次语音播报失败：{st.session_state.last_tts_error}")
        if st.button("重试语音播报", use_container_width=True):
            with st.spinner("正在重试语音播报（TTS）..."):
                tts_retry = synthesize_speech(st.session_state.pending_tts_text)
            if tts_retry["ok"]:
                st.success("语音播报重试成功。")
                st.audio(tts_retry["audio_bytes"], format="audio/mp3")
                st.session_state.pending_tts_text = ""
                st.session_state.last_tts_error = ""
            else:
                st.session_state.last_tts_error = tts_retry["error"]
                st.error(f"重试失败：{tts_retry['error']}")

# 4. 将缓存中的历史消息渲染到界面上
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # 如果有思考过程，用折叠面板展示
        if msg.get("reasoning"):
            with st.expander("🤔 查看大牛的内心思考过程"):
                st.markdown(msg["reasoning"])
        st.markdown(msg["content"])

# 5. 处理用户的输入并触发 Agent
typed_prompt = st.chat_input("请输入您的问题，例如：Gemma 4 在端侧有什么多模态进展？")
prompt = typed_prompt or st.session_state.pending_voice_prompt or st.session_state.pending_action_prompt
if prompt:
    is_user_direct_prompt = bool(typed_prompt or st.session_state.pending_voice_prompt)
    set_thread_id(session_id)
    st.session_state.task_runtime = {"step_timeline": [], "last_failure_summary": ""}
    st.session_state.pending_voice_prompt = ""
    payload_ctx = _consume_pending_context()

    # Week7-2: 自动偏好学习（仅针对用户直接输入，不对系统自动追问生效）
    if is_user_direct_prompt:
        _auto_learn_user_preferences(session_id, prompt)

    relevant_memory_notes = select_relevant_memory_notes(
        st.session_state.get("current_memory_notes", []),
        prompt,
        top_k=5,
    )
    st.session_state.last_relevant_memory_notes = relevant_memory_notes
    if relevant_memory_notes:
        st.caption(f"已召回相关长期记忆 {len(relevant_memory_notes)} 条。")
    
    # 将用户的问题马上显示在页面上
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 显示一个正在运行的占位提示框
    with st.chat_message("assistant"):
        status_container = st.empty()
        status_container.info("🧠 Agent 已接收任务，正在规划...")
        
        final_answer = ""
        reasoning_text = ""
        
        try:
            log_event("main_web", "user_query", meta={"thread_id": session_id, "chars": len(prompt)})
            # 运行 Agent，并实时捕获节点状态
            input_payload = _build_agent_input_payload(prompt, relevant_memory_notes, payload_ctx)
            for output in agent_app.stream(input_payload, config=config, stream_mode="updates"):
                for node_name, node_state in output.items():
                    # 实时回写任务状态与时间线
                    update_task_runtime_from_node(node_name, node_state, st.session_state.task_runtime)
                    _apply_action_updates_from_node_state(node_state)

                    # 👉 实时把 Agent 当前运行到哪个节点，反馈给前端用户！
                    status_item = _status_text_for_node(node_name)
                    if status_item:
                        status_level, status_text = status_item
                        if status_level == "warning":
                            status_container.warning(status_text)
                        else:
                            status_container.info(status_text)

                    if node_name == "synthesizer":
                        # 提取最终回答和思考过程
                        latest_msg = node_state["messages"][-1]
                        final_answer = latest_msg.content
                        reasoning_text = latest_msg.additional_kwargs.get("reasoning_content", "")
            
            # Agent 运行结束，清空提示框
            status_container.empty()
            
            # 渲染思考过程（如果有）
            if reasoning_text:
                with st.expander("🤔 查看大牛的内心思考过程"):
                    st.markdown(reasoning_text)
                    
            # 渲染正式回答
            st.markdown(final_answer)

            # 语音播报（开启语音能力时）
            if VOICE_ENABLED and st.session_state.voice_auto_tts and final_answer.strip():
                status_container.info("🔊 正在生成语音播报（TTS）...")
                tts_result = synthesize_speech(final_answer)
                if tts_result["ok"]:
                    st.audio(tts_result["audio_bytes"], format="audio/mp3")
                    st.session_state.pending_tts_text = ""
                    st.session_state.last_tts_error = ""
                else:
                    st.caption(f"语音播报不可用：{tts_result['error']}")
                    st.session_state.pending_tts_text = final_answer
                    st.session_state.last_tts_error = tts_result["error"]
            
            # 把 AI 的回答存入前端缓存
            st.session_state.messages.append({
                "role": "assistant", 
                "content": final_answer,
                "reasoning": reasoning_text
            })

        except Exception as e:
            log_event("main_web", "error", meta={"thread_id": session_id, "error": str(e)})
            st.error(f"Agent 运行出错: {e}")