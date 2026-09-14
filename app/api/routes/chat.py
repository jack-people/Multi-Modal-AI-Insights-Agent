import json
from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse
from app.api.deps import get_agent_runner
from app.api.schemas.chat import ChatRequest, ChatResponse
from app.api.schemas.error import ApiErrorResponse
from app.service.agent_runner import AgentRunner

router = APIRouter(prefix="/v1/sessions", tags=["chat"])


@router.post(
    "/{session_id}/chat",
    response_model=ChatResponse,
    responses={
        422: {"model": ApiErrorResponse, "description": "请求参数错误"},
        500: {"model": ApiErrorResponse, "description": "服务内部异常"},
    },
)
def chat(
    session_id: str,
    req: ChatRequest = Body(
        ...,
        examples=[
            {
                "message": "请总结最近多模态Agent进展",
            },
            {
                "message": "请结合这张图给出结论",
                "inputs": {
                    "vision_context": "图中包含2026年Q1-Q2销量对比",
                    "vision_mode": "chart",
                },
            },
        ],
    ),
    runner: AgentRunner = Depends(get_agent_runner),
):
    snapshot = runner.run_chat(session_id, req)
    return ChatResponse(
        session_id=session_id,
        answer=snapshot.get("last_answer", ""),
        reasoning=snapshot.get("last_reasoning", ""),
        task_runtime=snapshot.get("task_runtime", {}),
    )


@router.post(
    "/{session_id}/stream",
    responses={
        422: {"model": ApiErrorResponse, "description": "请求参数错误"},
        500: {"model": ApiErrorResponse, "description": "服务内部异常"},
    },
)
def chat_stream(
    session_id: str,
    req: ChatRequest = Body(
        ...,
        examples=[
            {
                "message": "请一步步分析并输出执行过程",
            }
        ],
    ),
    runner: AgentRunner = Depends(get_agent_runner),
):
    def event_gen():
        for event in runner.stream_chat(session_id, req):
            event_name = event.get("type", "message")
            payload = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_name}\ndata: {payload}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
