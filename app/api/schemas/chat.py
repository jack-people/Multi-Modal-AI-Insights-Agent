from typing import Any
from pydantic import BaseModel, Field


class ChatInputs(BaseModel):
    vision_context: str | None = None
    vision_image_name: str | None = None
    vision_mode: str | None = None
    vision_ocr_text: str | None = None
    vision_key_points: list[str] | None = None
    vision_chart_insights: list[str] | None = None
    vision_uncertainties: list[str] | None = None
    action_results: list[dict[str, Any]] | None = None
    user_profile: dict[str, Any] | None = None
    user_memory_notes: list[str] | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="用户输入文本")
    inputs: ChatInputs | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"message": "请总结最近多模态Agent进展"},
                {
                    "message": "请分析这张图",
                    "inputs": {
                        "vision_context": "图中是季度销量条形图",
                        "vision_mode": "chart",
                    },
                },
            ]
        }
    }


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    reasoning: str = ""
    task_runtime: dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "demo",
                "answer": "截至2026年6月，多模态Agent进入工程化提效阶段。",
                "reasoning": "",
                "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
            }
        }
    }
