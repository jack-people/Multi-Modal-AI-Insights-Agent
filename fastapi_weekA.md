# FastAPI Week A（已落地）

## 已实现接口
- `GET /healthz`
- `GET /readyz`
- `POST /v1/sessions/{session_id}/chat`
- `GET /v1/sessions/{session_id}/state`

## 运行方式
- 启动命令（示例）：
  - `uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload`

## 请求示例
```bash
curl -X POST "http://127.0.0.1:8000/v1/sessions/demo/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"请总结最近多模态Agent进展\"}"
```

## 说明
- FastAPI 壳层复用现有 `graph.py`、`web_task_runtime.py`。
- `/state` 返回该会话最近一次 `/chat` 的快照状态（内存态）。
