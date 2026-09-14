from datetime import datetime
from langchain_core.messages import SystemMessage
from model import llm_router
from state import AgentState
from tools import tools
from skill_manager import skill_manager
from runtime_context import log_event
from .common import retry_count

llm_with_tools = llm_router.bind_tools(tools)


def skill_execution_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("executor", "start", retry_count=current_retry, meta={"active_skill": state.get("active_skill", "none")})
    try:
        active_skill = state.get("active_skill", "none")
        messages = state["messages"]
        task_plan = state.get("task_plan", [])
        current_step = state.get("current_step", 0)
        action_results = state.get("action_results", []) or []
        current_step_text = ""
        if task_plan and 0 <= current_step < len(task_plan):
            current_step_text = task_plan[current_step]

        current_date = datetime.now().strftime("%Y年%m月%d日")

        if active_skill == "none" or active_skill == "":
            system_instruction = f"""你是贾维斯，一个专业的多模态AI研究助理。
今天是 {current_date}。

【行动规范】：
1. 你可以调用工具检索最新信息来回答用户。
1.1 当用户明确要求“保存文件/生成邮件草稿/执行动作”时，你应优先使用 action_* 工具，而不是只给建议。
1.2 对于返回 requires_confirmation=true 的动作，不要假装已执行成功；应明确告知用户“待确认”。
2. ⚠️ 极其重要：一旦你认为已经收集到了【足够且相关】的信息，必须**立即停止**调用工具！
3. 停止调用工具的方式是：直接输出一段纯文本（总结你收集到的内容），系统会自动将你的文本交给总结器(Synthesizer)。
4. 绝对禁止为了追求完美而进行超过 3 次的无意义重复检索！"""
        else:
            sop_content = skill_manager.get_skill_sop(active_skill)
            system_instruction = f"""你是贾维斯。今天是 {current_date}。
你正在执行专属技能：【{active_skill}】。

请严格遵循以下 SOP 执行任务：
{sop_content}

【行动规范】：
⚠️ 极其重要：当你完成了 SOP 要求的检索步骤，或者认为收集的数据已经足够时，必须**立即停止**调用工具！
如果用户请求执行动作，优先使用 action_* 工具。若动作结果是待确认，必须如实说明“尚未执行”。
直接输出你的分析结论文本（不带工具调用），系统会自动进入下一步。"""

        if task_plan:
            system_instruction += f"""

【任务计划摘要】：
{state.get("task_plan_summary", "")}

【当前步骤】：
步骤 {current_step + 1}/{len(task_plan)}: {current_step_text}

【执行要求】：
- 优先完成当前步骤，再决定是否进入下一步骤。
- 若需要工具，先调用工具；若当前步骤完成，输出自然语言结论并停止工具调用。"""
        if action_results:
            system_instruction += f"""

【最近动作执行结果】：
{action_results}
请基于这些结果继续完成任务；若动作失败或被拒绝，给出替代方案。"""

        print(f"⚙️ 贾维斯 Executor 加载 [{active_skill}] 技能上下文...")
        system_message = SystemMessage(content=system_instruction)
        filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        current_messages = [system_message] + filtered_messages

        response = llm_with_tools.invoke(current_messages)
        has_tool_calls = bool(getattr(response, "tool_calls", None))
        step_status = "in_progress" if has_tool_calls else "awaiting_review"

        log_event(
            "executor",
            "done",
            retry_count=current_retry,
            meta={"has_tool_calls": has_tool_calls, "current_step": current_step, "step_status": step_status},
        )
        return {
            "messages": [response],
            "current_step": current_step,
            "step_status": step_status,
        }
    except Exception as e:
        log_event("executor", "error", retry_count=current_retry, meta={"error": str(e)})
        raise


def router_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("router", "start", retry_count=current_retry)
    try:
        print("🤖 [Router] 正在思考调用什么工具 (或如何修正)...")

        sys_msg = SystemMessage(content="""你是多模态AI领域的智能助手。
【搜索决策准则】：
1 所有问题必须先调用search_dify_arxiv_db去知识库里检索相关论文，绝对不允许直接回答或放弃！
2. **时效性判定**：涉及最新发布、未来计划或你不确定的专有名词，必须先调用`search_web_news` 去网上搜索！绝对不允许凭空猜测或直接放弃！。
3. **容错搜索**：如果用户提问中疑似包含拼写错误或不存在的型号，请在搜索时尝试使用你认为正确的术语，或搜索该系列产品的“最新版本”或“发布路线图”。
4. **失败演进**：如果收到审查未通过的反馈，严禁重复之前的搜索词。请尝试：
   - 扩大关键词范围（从具体型号扩大到系列品牌）。
   - 改变搜索维度（从“参数亮点”转向“官方发布新闻”或“技术预测”）。
   - 拆分复杂问题。 """)

        messages = [sys_msg] + state["messages"]
        response = llm_with_tools.invoke(messages)
        log_event("router", "done", retry_count=current_retry)
        return {"messages": [response]}
    except Exception as e:
        log_event("router", "error", retry_count=current_retry, meta={"error": str(e)})
        raise
