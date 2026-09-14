from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz():
    return {"ok": True, "service": "multi-modal-ai-insights-agent-api"}


@router.get("/readyz")
def readyz():
    return {"ready": True}
