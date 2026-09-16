import os
import sys
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 兼容 `python app/api/main.py` 直跑方式
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import (
    validate_config,
    API_AUTH_ENABLED,
    API_AUTH_KEY,
    API_RATE_LIMIT_PER_MIN,
    API_CORS_ORIGINS,
)
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.actions import router as actions_router
from app.api.exceptions import ApiError
from app.api.middleware import FixedWindowRateLimiter
from runtime_context import log_event, set_request_id, set_session_hint
from mcp_tools.factory import create_mcp
from mcp_tools.registry import DSH_HTTP_TOOL_NAMES
from contextlib import asynccontextmanager


def create_api_app() -> FastAPI:
    validate_config(strict=False)

    dsh_mcp, _ = create_mcp(include=DSH_HTTP_TOOL_NAMES)
    mcp_asgi = dsh_mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with dsh_mcp.session_manager.run():
            yield

    app = FastAPI(
        title="Multi-Modal AI Insights Agent API",
        version="0.1.0",
        description="Week D FastAPI：统一错误码 + 流式协议 + 鉴权/限流/请求追踪；/v1/mcp 供 dsh 使用",
        lifespan=lifespan,
    )
    limiter = FixedWindowRateLimiter(API_RATE_LIMIT_PER_MIN)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=API_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-Id",
            "X-Process-Time-Ms",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
        ],
    )

    @app.middleware("http")
    async def api_guard(request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        set_request_id(request_id)
        session_hint = request.headers.get("X-Session-Id") or request.headers.get("mcp-session-id") or ""
        set_session_hint(session_hint)
        path = request.url.path

        def _json_error(status_code: int, error_code: str, message: str, detail: dict | None = None):
            body = {
                "ok": False,
                "error_code": error_code,
                "message": message,
                "detail": detail or {},
            }
            return JSONResponse(status_code=status_code, content=body, headers={"X-Request-Id": request_id})

        if path.startswith("/v1/"):
            if API_AUTH_ENABLED:
                got = request.headers.get("X-API-Key", "")
                if got != API_AUTH_KEY:
                    log_event("fastapi_api", "unauthorized", meta={"path": path, "request_id": request_id})
                    return _json_error(401, "MM401_UNAUTHORIZED", "缺少或无效的 API Key")

            client_ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                         or (request.client.host if request.client else "unknown"))
            allowed, remaining, retry_after = limiter.check(client_ip)
            if not allowed:
                log_event("fastapi_api", "rate_limited", meta={"path": path, "request_id": request_id, "ip": client_ip})
                return JSONResponse(
                    status_code=429,
                    content={
                        "ok": False,
                        "error_code": "MM429_RATE_LIMITED",
                        "message": "请求过于频繁，请稍后重试",
                        "detail": {"retry_after_sec": retry_after},
                    },
                    headers={
                        "X-Request-Id": request_id,
                        "X-RateLimit-Limit": str(API_RATE_LIMIT_PER_MIN),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(retry_after),
                    },
                )
            request.state.rate_remaining = remaining
        else:
            request.state.rate_remaining = None

        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
        if path.startswith("/v1/"):
            response.headers["X-RateLimit-Limit"] = str(API_RATE_LIMIT_PER_MIN)
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_remaining)
        log_event(
            "fastapi_api",
            "request_done",
            meta={"path": path, "status_code": response.status_code, "request_id": request_id, "elapsed_ms": elapsed_ms},
        )
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "ok": False,
                "error_code": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error_code": "MM422_VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "detail": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error_code": "MM500_INTERNAL_ERROR",
                "message": "服务内部异常",
                "detail": {"error": str(exc)},
            },
        )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(actions_router)
    app.mount("/v1/mcp", mcp_asgi)
    app.state.dsh_mcp = dsh_mcp
    return app


app = create_api_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )

