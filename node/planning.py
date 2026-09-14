from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from model import llm_router
from state import AgentState
from skill_manager import skill_manager
from runtime_context import log_event
from .common import retry_count


class RouteDecision(BaseModel):
    selected_skill: str = Field(description="选定的技能名称。如果不匹配任何技能，严格返回 'none'")


class PlanOutput(BaseModel):
    summary: str = Field(description="任务执行摘要，1-2句话。")
    steps: list[str] = Field(description="执行步骤列表，建议 2-4 步。")


def intent_router_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("intent_router", "start", retry_count=current_retry)
    try:
        print("🧭 贾维斯 Router 正在分析用户意图...")
        route_parser = PydanticOutputParser(pydantic_object=RouteDecision)

        user_message = state["messages"][-1].content
        descriptions = skill_manager.get_all_descriptions()
        format_instructions = route_parser.get_format_instructions()

        prompt = f"""你是一个智能路由。请分析用户输入，并从以下技能库中挑选最合适的一个。
【可用技能库】：
{descriptions}

【输出要求】
{format_instructions}

用户输入：{user_message}"""

        response = llm_router.invoke(prompt)

        try:
            decision = route_parser.parse(response.content)
            skill_name = decision.selected_skill
        except Exception:
            print("⚠️ 路由解析失败，降级为无技能模式。")
            skill_name = "none"

        print(f"🎯 命中技能: [{skill_name}]")
        log_event("intent_router", "done", retry_count=current_retry, meta={"active_skill": skill_name})
        return {"active_skill": skill_name}
    except Exception as e:
        log_event("intent_router", "error", retry_count=current_retry, meta={"error": str(e)})
        raise


def planner_node(state: AgentState):
    current_retry = retry_count(state)
    log_event("planner", "start", retry_count=current_retry, meta={"active_skill": state.get("active_skill", "none")})
    try:
        parser = PydanticOutputParser(pydantic_object=PlanOutput)
        user_message = state["messages"][-1].content
        active_skill = state.get("active_skill", "none")

        prompt = f"""你是任务规划器。请针对用户问题生成一个简明执行计划。
当前技能：{active_skill}
用户问题：{user_message}

要求：
1. steps 必须是可执行的短句，2-4步。
2. summary 用 1-2 句话概括整体执行思路。
3. 若问题简单，也至少输出2步（检索 -> 归纳）。

请严格按以下格式输出：
{parser.get_format_instructions()}
"""

        response = llm_router.invoke(prompt)
        try:
            plan = parser.parse(response.content)
        except Exception:
            log_event("planner", "parse_fallback", retry_count=current_retry)
            plan = PlanOutput(
                summary="先收集信息，再总结回答。",
                steps=["检索相关信息", "整理并给出回答"],
            )

        task_plan = [step.strip() for step in plan.steps if step.strip()]
        if not task_plan:
            task_plan = ["检索相关信息", "整理并给出回答"]

        log_event("planner", "done", retry_count=current_retry, meta={"steps": len(task_plan)})
        return {
            "task_plan": task_plan,
            "task_plan_summary": plan.summary,
            "current_step": 0,
            "step_status": "planned",
        }
    except Exception as e:
        log_event("planner", "error", retry_count=current_retry, meta={"error": str(e)})
        raise
