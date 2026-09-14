from fastapi import APIRouter, Depends
from app.api.deps import get_agent_runner
from app.api.exceptions import ApiError
from app.api.schemas.action import ActionDecisionResponse
from app.api.schemas.error import ApiErrorResponse
from app.service.agent_runner import AgentRunner

router = APIRouter(prefix="/v1/sessions", tags=["actions"])


@router.post(
    "/{session_id}/actions/{action_id}/confirm",
    response_model=ActionDecisionResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "动作不存在"},
        500: {"model": ApiErrorResponse, "description": "服务内部异常"},
    },
)
def confirm_action(session_id: str, action_id: str, runner: AgentRunner = Depends(get_agent_runner)):
    result = runner.confirm_action(session_id, action_id, approve=True)
    if not bool(result.get("ok", False)):
        raise ApiError(
            http_status=404,
            error_code="MM404_ACTION_NOT_FOUND",
            message=result.get("message", "动作不存在"),
            detail={"session_id": session_id, "action_id": action_id},
        )
    return ActionDecisionResponse(
        ok=bool(result.get("ok", False)),
        session_id=session_id,
        action_id=action_id,
        message=result.get("message", ""),
        result=result.get("result", {}),
    )


@router.post(
    "/{session_id}/actions/{action_id}/reject",
    response_model=ActionDecisionResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "动作不存在"},
        500: {"model": ApiErrorResponse, "description": "服务内部异常"},
    },
)
def reject_action(session_id: str, action_id: str, runner: AgentRunner = Depends(get_agent_runner)):
    result = runner.confirm_action(session_id, action_id, approve=False)
    if not bool(result.get("ok", False)):
        raise ApiError(
            http_status=404,
            error_code="MM404_ACTION_NOT_FOUND",
            message=result.get("message", "动作不存在"),
            detail={"session_id": session_id, "action_id": action_id},
        )
    return ActionDecisionResponse(
        ok=bool(result.get("ok", False)),
        session_id=session_id,
        action_id=action_id,
        message=result.get("message", ""),
        result=result.get("result", {}),
    )
