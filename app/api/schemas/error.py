from typing import Any
from pydantic import BaseModel, Field


class ApiErrorResponse(BaseModel):
    ok: bool = False
    error_code: str = Field(description="稳定错误码，供前端分支处理")
    message: str = Field(description="面向用户或调用方的错误说明")
    detail: dict[str, Any] = Field(default_factory=dict, description="可选上下文信息")
