from typing import Any
from pydantic import BaseModel, Field


class ActionDecisionResponse(BaseModel):
    ok: bool
    session_id: str
    action_id: str = ""
    message: str = ""
    result: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "example": {
                "ok": True,
                "session_id": "demo",
                "action_id": "act_123456789abc",
                "message": "",
                "result": {
                    "action": "action_write_report_file",
                    "status": "executed",
                    "message": "文件写入成功: action_outputs/report.md",
                    "output_path": "action_outputs/report.md",
                    "command_output": "",
                },
            }
        }
    }
