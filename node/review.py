from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from model import llm_router, llm_synthesizer
from config import MAX_CRITIC_RETRIES
from state import AgentState, CriticOutput
from runtime_context import log_event
from .common import (
    retry_count,
    get_latest_question,
    build_dialog_context,
    build_tool_context,
    collect_evidence,
    collect_vision_evidence,
    collect_action_evidence,
    format_evidence_for_prompt,
    extract_cited_evidence_ids,
)


def _build_multimodal_context(state: AgentState) -> dict:
    return {
        "vision_context": str(state.get("vision_context", "")).strip(),
        "vision_image_name": str(state.get("vision_image_name", "")).strip(),
        "vision_mode": str(state.get("vision_mode", "general")).strip(),
        "vision_ocr_text": str(state.get("vision_ocr_text", "")).strip(),
        "vision_key_points": state.get("vision_key_points", []),
        "vision_chart_insights": state.get("vision_chart_insights", []),
        "vision_uncertainties": state.get("vision_uncertainties", []),
    }


def _build_evidence_bundle(state: AgentState) -> dict:
    evidence_items = collect_evidence(state["messages"])
    vision_evidence_items = collect_vision_evidence(state)
    action_evidence_items = collect_action_evidence(state)
    all_evidence_items = evidence_items + vision_evidence_items + action_evidence_items
    return {
        "all_items": all_evidence_items,
        "prompt": format_evidence_for_prompt(all_evidence_items),
    }


def synthesizer_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("synthesizer", "start", retry_count=current_retry)
    try:
        print("\n" + "=" * 50)
        print("🧠 [Synthesizer 模型 (deepseek-reasoner)] 开始深度思考...")
        print("=" * 50)

        latest_question = get_latest_question(state["messages"])
        context_str = build_dialog_context(state["messages"])
        evidence_bundle = _build_evidence_bundle(state)
        evidence_prompt = evidence_bundle["prompt"]
        mm_ctx = _build_multimodal_context(state)
        vision_context = mm_ctx["vision_context"]
        vision_image_name = mm_ctx["vision_image_name"]
        vision_mode = mm_ctx["vision_mode"]
        vision_ocr_text = mm_ctx["vision_ocr_text"]
        vision_key_points = mm_ctx["vision_key_points"]
        vision_chart_insights = mm_ctx["vision_chart_insights"]
        vision_uncertainties = mm_ctx["vision_uncertainties"]
        user_profile = state.get("user_profile", {}) or {}
        answer_style = str(user_profile.get("answer_style", "balanced")).strip()
        tone = str(user_profile.get("tone", "professional")).strip()
        use_structure = bool(user_profile.get("use_structure", True))
        user_memory_notes = state.get("user_memory_notes", []) or []
        if not context_str:
            context_str = "未调用任何外部工具，请凭借你的内部知识库进行解答。"

        current_date = datetime.now().strftime("%Y年%m月%d日")
        prompt = f"""你是多模态AI领域的技术大牛。
                 当前系统日期是：{current_date}。
                 请根据以下收集到的参考资料，为用户撰写一份专业、
                 全面、且带有学术深度的解答。必须指出最新进展，
                 并对未来的趋势做简要点评。

【撰写原则】：
1. **事实优先**：如果搜索资料显示用户询问的特定版本、型号或事件尚未发生或不存在，请务必礼貌地指出。不要为了迎合用户而虚构。
2. **关联引导**：若用户询问的实体不存在，请提供最接近的已知现状或官方最新动态作为替代参考。
3. **深度点评**：在回答现状的基础上，结合多模态领域的技术趋势进行简要点评。
4. **拒绝幻觉**：资料中未提及的信息，请明确表示“暂无公开信息”。
5. **拒绝重复**：绝对不允许出现重复的段落或句子！如果你发现自己在重复上一条内容，请立即停止并进行下一条。
6. **证据引用**：凡是基于证据得出的结论，必须用证据编号标注来源（文本证据 [E#]、视觉证据 [V#]、动作证据 [A#]）。
7. **多模态融合**：若存在图片解析结果，请将图像信息与文本证据融合分析，避免只复述其中一方。
8. **时间一致性**：涉及“最新/截至目前”的表述时，必须以当前系统日期为基准，避免引用过期年份作为“最新”。

【用户偏好】：
- answer_style={answer_style}（concise=简洁, balanced=均衡, detailed=详细）
- tone={tone}（professional=专业, casual=轻松）
- use_structure={use_structure}（True 时优先分点、分段输出）
请在不牺牲事实与证据质量的前提下，尽量贴合上述偏好。

【用户长期记忆】：
{user_memory_notes or ["无"]}
当这些记忆与本轮任务相关时，请优先对齐；若冲突，以用户本轮最新明确指令为准。

【输出格式要求】：
- 先给“核心结论”。
- 再给“关键依据”，每条依据后必须附上对应证据编号（如 [E1]、[V1]、[A1]）。
- 最后给“局限与未公开信息”。

【最新追问】: {latest_question}
【视觉上下文】(若为空表示本轮无图片):
image_name={vision_image_name}
vision_mode={vision_mode}
vision_context={vision_context or "无"}
vision_ocr_text={vision_ocr_text or "无"}
vision_key_points={vision_key_points or []}
vision_chart_insights={vision_chart_insights or []}
vision_uncertainties={vision_uncertainties or []}
【结构化证据清单】:
{evidence_prompt}
【对话历史与参考资料】: {context_str}
"""

        response_chunks = []
        for chunk in llm_synthesizer.stream([HumanMessage(content=prompt)]):
            reasoning = chunk.additional_kwargs.get("reasoning_content", "")
            content = chunk.content

            if reasoning:
                print(f"\033[90m{reasoning}\033[0m", end="", flush=True)
            if content:
                print(content, end="", flush=True)
            response_chunks.append(chunk)

        final_message = response_chunks[0]
        for chunk in response_chunks[1:]:
            final_message += chunk

        print("\n" + "=" * 50)
        log_event("synthesizer", "done", retry_count=current_retry)
        return {"messages": [final_message]}
    except Exception as e:
        log_event("synthesizer", "error", retry_count=current_retry, meta={"error": str(e)})
        raise


def critic_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("critic", "start", retry_count=current_retry)
    try:
        print("\n🕵️ [Critic] 正在严格审查 Synthesizer 生成的答案...")

        latest_question = get_latest_question(state["messages"])
        last_answer = state["messages"][-1].content
        context_str = build_tool_context(state["messages"]) or "暂无外部参考资料。"
        evidence_bundle = _build_evidence_bundle(state)
        all_evidence_items = evidence_bundle["all_items"]
        evidence_prompt = evidence_bundle["prompt"]
        mm_ctx = _build_multimodal_context(state)
        vision_context = mm_ctx["vision_context"]
        vision_image_name = mm_ctx["vision_image_name"]
        vision_mode = mm_ctx["vision_mode"]
        vision_ocr_text = mm_ctx["vision_ocr_text"]
        vision_key_points = mm_ctx["vision_key_points"]
        vision_chart_insights = mm_ctx["vision_chart_insights"]
        vision_uncertainties = mm_ctx["vision_uncertainties"]
        cited_ids = extract_cited_evidence_ids(last_answer)
        total_evidence = len(all_evidence_items)
        matched_ids = sorted(cited_ids.intersection({item["id"] for item in all_evidence_items}))
        coverage_ratio = (len(matched_ids) / total_evidence) if total_evidence else 1.0
        evidence_items_brief = [
            {
                "id": item.get("id", ""),
                "source": item.get("source", ""),
                "query": item.get("query", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in all_evidence_items
        ]
        evidence_meta = {
            "evidence_total": total_evidence,
            "evidence_matched": len(matched_ids),
            "evidence_coverage": round(coverage_ratio, 4),
            "evidence_items": evidence_items_brief,
            "evidence_cited_ids": sorted(cited_ids),
            "evidence_matched_ids": matched_ids,
        }

        current_date = datetime.now().strftime("%Y年%m月%d日")
        parser = PydanticOutputParser(pydantic_object=CriticOutput)
        prompt = f"""你是一个极其苛刻的AI内容审查专家。
当前系统时间是：{current_date}。
请评估以下生成的答案是否完美解答了用户【最新】的提问。
【核心审查准则】：
1. **纠错合规性**：如果用户询问的实体在现实中不存在，而 AI 正确指出了该错误并提供了最相关的准确信息，这被视为“精准对齐”，应予以 ACCEPT。
2. **拒绝敷衍**：如果回答包含“未查到”、“作为一个AI无法获取最新信息”等推托词，但在参考资料中其实存在相关线索，必须 REJECT。
3. **禁止推演**：如果 AI 在资料不足的情况下，将“猜测”当作“事实”来回答用户询问的具体型号，必须 REJECT。
4. **信息来源**：答案是否体现了最新搜索资料中的实质性内容？
5. **证据覆盖率**：若存在证据，回答中应出现证据编号引用（如 [E1]、[V1]、[A1]）。若完全没有引用，必须 REJECT。
6. **视觉一致性**：若存在视觉上下文，回答应体现关键视觉信息，且不得与视觉内容明显冲突。

用户最新提问: {latest_question}
工具收集到的参考资料: {context_str}
视觉上下文: image_name={vision_image_name}; vision_mode={vision_mode}; vision_context={vision_context or "无"}; vision_ocr_text={vision_ocr_text or "无"}; vision_key_points={vision_key_points or []}; vision_chart_insights={vision_chart_insights or []}; vision_uncertainties={vision_uncertainties or []}
结构化证据列表: {evidence_prompt}
最新生成的答案: {last_answer}
检测到的证据引用: {sorted(cited_ids)}
证据覆盖率: {coverage_ratio:.2f}（匹配 {len(matched_ids)} / 总证据 {total_evidence}）

【重要指令】
请严格按照以下JSON格式输出你的审查结果，不要包含任何多余的解释性文字：
{parser.get_format_instructions()}
请严格打分（0-10分），并给出审查决定。
"""

        llm_json = llm_router.bind(response_format={"type": "json_object"})
        response = llm_json.invoke([HumanMessage(content=prompt)])

        try:
            evaluation = parser.parse(response.content)
        except Exception as e:
            print(f"   -> ⚠️ 解析 Critic 输出失败，默认放行。错误: {e}")
            log_event("critic", "done", retry_count=current_retry, meta={"decision": "ACCEPT", "parse_failed": True})
            return {
                "critic_decision": "ACCEPT",
                "step_status": state.get("step_status", "in_progress"),
                "critic_score": 8,
                "critic_feedback": "解析失败，默认放行",
                **evidence_meta,
            }

        print(f"   -> 审查得分: {evaluation.score}/10")

        # 本地硬性规则：存在外部证据但回答未引用任何证据编号，直接打回
        if total_evidence > 0 and not matched_ids:
            feedback = "回答未引用任何证据编号（如 [E1]、[V1]、[A1]），证据覆盖率为 0。请基于证据重写并标注来源。"
            next_retry = current_retry + 1
            if next_retry >= MAX_CRITIC_RETRIES:
                log_event(
                    "critic",
                    "done",
                    retry_count=next_retry,
                    meta={"decision": "ACCEPT", "max_retry_reached": True, "reason": "coverage_guard_bypassed"},
                )
                return {
                    "critic_decision": "ACCEPT",
                    "retry_count": next_retry,
                    "step_status": "completed",
                    "critic_score": evaluation.score,
                    "critic_feedback": "达到最大重试次数，覆盖率规则放行",
                    **evidence_meta,
                }

            feedback_msg = HumanMessage(
                content=f"【Critic 审查未通过】由于以下原因，你的上一轮工作不及格：\n{feedback}\n请立刻根据建议更换搜索策略重新查询！"
            )
            log_event(
                "critic",
                "done",
                retry_count=next_retry,
                meta={"decision": "REJECT", "reason": "coverage_guard", "coverage": coverage_ratio},
            )
            return {
                "messages": [feedback_msg],
                "critic_decision": "REJECT",
                "retry_count": next_retry,
                "current_step": state.get("current_step", 0),
                "step_status": "needs_retry",
                "critic_score": evaluation.score,
                "critic_feedback": feedback,
                **evidence_meta,
            }

        if evaluation.score < 8 or evaluation.action == "REJECT":
            next_retry = current_retry + 1
            if next_retry >= MAX_CRITIC_RETRIES:
                print(
                    f"   -> ⚠️ 警告：已达到最大重试次数({MAX_CRITIC_RETRIES})，"
                    "为防止死循环，强制 ACCEPT。"
                )
                log_event("critic", "done", retry_count=next_retry, meta={"decision": "ACCEPT", "max_retry_reached": True})
                return {
                    "critic_decision": "ACCEPT",
                    "retry_count": next_retry,
                    "step_status": "completed",
                    "critic_score": evaluation.score,
                    "critic_feedback": "达到最大重试次数，强制放行",
                    **evidence_meta,
                }

            print(f"   -> ❌ 审查未通过，打回重做！当前重试次数: {next_retry}，反馈建议: {evaluation.feedback}")
            feedback_msg = HumanMessage(
                content=f"【Critic 审查未通过】由于以下原因，你的上一轮工作不及格：\n{evaluation.feedback}\n请立刻根据建议更换搜索策略重新查询！"
            )
            log_event("critic", "done", retry_count=next_retry, meta={"decision": "REJECT", "score": evaluation.score})
            return {
                "messages": [feedback_msg],
                "critic_decision": "REJECT",
                "retry_count": next_retry,
                "current_step": state.get("current_step", 0),
                "step_status": "needs_retry",
                "critic_score": evaluation.score,
                "critic_feedback": evaluation.feedback,
                **evidence_meta,
            }

        print("   -> ✅ 审查通过，准备输出给用户。")
        current_step = state.get("current_step", 0)
        task_plan = state.get("task_plan", [])
        if task_plan and current_step < len(task_plan) - 1:
            next_step = current_step + 1
            step_status = "in_progress"
        else:
            next_step = current_step
            step_status = "completed"

        log_event(
            "critic",
            "done",
            retry_count=0,
            meta={"decision": "ACCEPT", "score": evaluation.score, "current_step": next_step, "step_status": step_status},
        )
        return {
            "critic_decision": "ACCEPT",
            "retry_count": 0,
            "current_step": next_step,
            "step_status": step_status,
            "critic_score": evaluation.score,
            "critic_feedback": evaluation.feedback,
            **evidence_meta,
        }
    except Exception as e:
        log_event("critic", "error", retry_count=current_retry, meta={"error": str(e)})
        raise
