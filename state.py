# 定义状态与数据结构
from typing import Annotated, Literal
try:
    from typing import TypedDict, NotRequired
except ImportError:
    from typing_extensions import TypedDict, NotRequired
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

StepStatus = Literal["planned", "in_progress", "awaiting_review", "needs_retry", "completed"]
CriticDecision = Literal["ACCEPT", "REJECT"]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    critic_decision: NotRequired[CriticDecision]
    active_skill: NotRequired[str]
    retry_count: NotRequired[int]
    task_plan: NotRequired[list[str]]
    task_plan_summary: NotRequired[str]
    current_step: NotRequired[int]
    step_status: NotRequired[StepStatus]
    vision_context: NotRequired[str]
    vision_image_name: NotRequired[str]
    vision_mode: NotRequired[str]
    vision_ocr_text: NotRequired[str]
    vision_key_points: NotRequired[list[str]]
    vision_chart_insights: NotRequired[list[str]]
    vision_uncertainties: NotRequired[list[str]]
    action_results: NotRequired[list[dict]]
    user_profile: NotRequired[dict]
    user_memory_notes: NotRequired[list[str]]
    critic_score: NotRequired[int]
    critic_feedback: NotRequired[str]
    evidence_total: NotRequired[int]
    evidence_matched: NotRequired[int]
    evidence_coverage: NotRequired[float]
    evidence_items: NotRequired[list[dict]]
    evidence_cited_ids: NotRequired[list[str]]
    evidence_matched_ids: NotRequired[list[str]]

class CriticOutput(BaseModel):
    score: int = Field(description="对回答的评分，0-10分。8分及以上为合格。")
    feedback: str = Field(description="如果不合格，请给出具体的改进建议或需要进一步搜索的关键词建议。如果合格，可以写'无'。")
    action: CriticDecision = Field(description="如果不合格填 'REJECT'，如果合格填 'ACCEPT'")