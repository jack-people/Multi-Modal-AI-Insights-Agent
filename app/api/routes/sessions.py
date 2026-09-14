from fastapi import APIRouter, Depends
from app.api.deps import get_agent_runner
from app.api.schemas.session import SessionStateResponse
from app.service.agent_runner import AgentRunner

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.get("/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str, runner: AgentRunner = Depends(get_agent_runner)):
    snapshot = runner.get_state(session_id)
    return SessionStateResponse(
        session_id=session_id,
        task_runtime=snapshot.get("task_runtime", {}),
        last_answer=snapshot.get("last_answer", ""),
        last_reasoning=snapshot.get("last_reasoning", ""),
        updated_at=snapshot.get("updated_at", ""),
        action_pending_queue=snapshot.get("action_pending_queue", []),
        action_execution_logs=snapshot.get("action_execution_logs", []),
    )
