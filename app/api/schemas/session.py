from typing import Any
from pydantic import BaseModel, Field


class SessionStateResponse(BaseModel):
    session_id: str
    task_runtime: dict[str, Any]
    last_answer: str = ""
    last_reasoning: str = ""
    updated_at: str = ""
    action_pending_queue: list[dict[str, Any]] = Field(default_factory=list)
    action_execution_logs: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "demo",
                "task_runtime": {"step_timeline": [], "last_failure_summary": ""},
                "last_answer": "",
                "last_reasoning": "",
                "updated_at": "2026-06-21T08:00:00",
                "action_pending_queue": [],
                "action_execution_logs": [],
            }
        }
    }
