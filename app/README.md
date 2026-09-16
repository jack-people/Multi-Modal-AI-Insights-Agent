# FastAPI 使用说明（Week D）

## 启动

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8001 --reload
```

## 访问地址

- 文档（Swagger UI）：`http://127.0.0.1:8001/docs`
- 文档（ReDoc）：`http://127.0.0.1:8001/redoc`
- 健康检查：`http://127.0.0.1:8001/healthz`

## 核心接口

- `GET /healthz`：基础健康检查
- `GET /readyz`：就绪探针
- `POST /v1/sessions/{session_id}/chat`：同步聊天
- `POST /v1/sessions/{session_id}/stream`：SSE 流式聊天
- `GET /v1/sessions/{session_id}/state`：会话快照（含待确认动作队列）
- `POST /v1/sessions/{session_id}/actions/{action_id}/confirm`：确认执行动作
- `POST /v1/sessions/{session_id}/actions/{action_id}/reject`：拒绝执行动作

## 快速测试

1) 先测 `GET /healthz`

2) 再测同步聊天 `POST /v1/sessions/demo/chat`，请求体示例：

```json
{
  "message": "请总结最近多模态Agent进展"
}
```

3) 调用 `GET /v1/sessions/demo/state` 查看：
- `task_runtime`
- `action_pending_queue`
- `action_execution_logs`

4) 若 `action_pending_queue` 非空，复制其中 `id`，调用：
- `POST /v1/sessions/demo/actions/{action_id}/confirm` 或
- `POST /v1/sessions/demo/actions/{action_id}/reject`

## SSE 事件协议（`/stream`）

- 协议版本：`mm-agent.stream.v1`
- 每条事件包含：`schema`、`seq`、`ts`、`type`、`session_id`、`data`
- SSE 帧格式使用 `event: <type>` + `data: <json>`
- 典型事件类型：
  - `run_started`
  - `node_update`
  - `planner_update`
  - `critic_update`
  - `synthesizer_update`
  - `action_required`
  - `action_result`
  - `run_completed`

示例（浏览器或前端 EventSource 消费到的单条数据体）：

```json
{
  "schema": "mm-agent.stream.v1",
  "seq": 7,
  "ts": "2026-06-21T08:00:00+00:00",
  "type": "action_required",
  "session_id": "demo",
  "data": {
    "action_id": "act_123456789abc",
    "action": "action_write_report_file",
    "risk": "high",
    "message": "该动作需要确认后执行"
  }
}
```

## 统一错误响应（Week D）

所有非 2xx 错误返回统一结构：

```json
{
  "ok": false,
  "error_code": "MM422_VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {}
}
```

当前约定错误码：

- `MM422_VALIDATION_ERROR`：请求参数不合法
- `MM404_ACTION_NOT_FOUND`：`action_id` 不存在或已处理
- `MM500_INTERNAL_ERROR`：服务内部异常
- `MM401_UNAUTHORIZED`：缺少或无效 API Key
- `MM429_RATE_LIMITED`：请求过于频繁

## D 阶段网关能力

- 鉴权：当 `API_AUTH_ENABLED=true` 时，`/v1/*` 必须带请求头 `X-API-Key`
- 限流：`/v1/*` 按 IP 固定窗口限流，阈值由 `API_RATE_LIMIT_PER_MIN` 控制
- 追踪：所有请求返回 `X-Request-Id` 与 `X-Process-Time-Ms`
- 限流响应头：`X-RateLimit-Limit`、`X-RateLimit-Remaining`、`Retry-After`

## 联调示例（curl）

1) 健康检查

```bash
curl -X GET "http://127.0.0.1:8001/healthz"
```

2) 同步聊天

```bash
curl -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_api_key_if_enabled>" \
  -d "{\"message\":\"请总结最近多模态Agent进展\"}"
```

3) SSE 流式聊天（命令行观察事件流）

```bash
curl -N -X POST "http://127.0.0.1:8001/v1/sessions/demo/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_api_key_if_enabled>" \
  -d "{\"message\":\"请一步步分析并输出执行过程\"}"
```

4) 查看会话状态（拿待确认动作 `action_id`）

```bash
curl -X GET "http://127.0.0.1:8001/v1/sessions/demo/state"
```

5) 确认/拒绝动作

```bash
curl -X POST "http://127.0.0.1:8001/v1/sessions/demo/actions/act_123456789abc/confirm"
curl -X POST "http://127.0.0.1:8001/v1/sessions/demo/actions/act_123456789abc/reject"
```

## 前端对接示例（EventSource）

浏览器原生 `EventSource` 仅支持 `GET`。当前 `/stream` 为 `POST`，推荐两种做法：

- 方案 A：前端用 `fetch` 读取 `ReadableStream`（推荐，支持 POST body）
- 方案 B：后端新增 `GET /stream` 包装路由（参数放 query），供 `EventSource` 直连

下面给出方案 A 的最小示例：

```javascript
async function startStream(sessionId, message) {
  const resp = await fetch(`/v1/sessions/${sessionId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const eventLine = frame.split("\n").find((l) => l.startsWith("event: "));
      const dataLine = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!eventLine || !dataLine) continue;

      const eventType = eventLine.replace("event: ", "").trim();
      const payload = JSON.parse(dataLine.replace("data: ", ""));
      console.log("[SSE]", eventType, payload);
    }
  }
}
```

## 推荐联调顺序

- 先打通 `healthz` 与 `chat`
- 再接 `stream` 实时展示节点状态
- 出现 `action_required` 后调用 `state` 拉取 `action_id`
- 调 `confirm/reject`，最后再发一轮 `chat` 让 Agent 消化动作结果

## 常见排查

- 终端需出现：`Uvicorn running on http://0.0.0.0:8001`
- 若浏览器打不开，检查防火墙或端口是否被占用















测试完整流程

很好，下面给你一套可逐项打勾的完整测试流程（按 Week A→D 全覆盖）。
你可以一条条执行，执行完回复我：第N步通过 或 第N步失败 + 返回内容，我再带你继续下一步。

0) 测试前准备（一次性）
0.1 启动服务
在项目根目录执行：

uvicorn app.api.main:app --host 0.0.0.0 --port 8001 --reload
预期：终端出现 Uvicorn running on http://0.0.0.0:8001

0.2 建议 .env（D阶段）最小配置
API_AUTH_ENABLED=false
API_RATE_LIMIT_PER_MIN=60
API_CORS_ORIGINS=*
1) Week A 基础可用性
1.1 健康检查
curl.exe http://127.0.0.1:8001/healthz
预期：HTTP 200，包含 ok: true

1.2 就绪检查
curl.exe http://127.0.0.1:8001/readyz
预期：HTTP 200，包含 ready: true

1.3 OpenAPI 文档
浏览器打开：

http://127.0.0.1:8001/docs
http://127.0.0.1:8001/redoc
预期：能看到 chat/state/stream/actions 接口

2) Week B 同步对话与状态
2.1 同步 chat
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"请总结最近多模态Agent进展\"}"
预期：

HTTP 200
返回含 session_id, answer, task_runtime
2.2 会话状态 state
curl.exe "http://127.0.0.1:8001/v1/sessions/demo/state"
预期：

HTTP 200
返回含 task_runtime, action_pending_queue, action_execution_logs
3) Week B 流式输出（SSE）
3.1 流式请求
curl.exe -N -X POST "http://127.0.0.1:8001/v1/sessions/demo/stream" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"请一步步分析并输出执行过程\"}"
预期（终端持续打印）：

有 event: run_started
有多个 event: node_update / planner_update / critic_update 等
最终有 event: run_completed
4) Week B 动作确认闭环（confirm/reject）
4.1 触发一个可能需要确认的动作
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"请帮我生成一份报告并写入文件report.md\"}"
4.2 查待确认队列
curl.exe "http://127.0.0.1:8001/v1/sessions/demo/state"
预期：action_pending_queue 里有 id（如 act_xxx）

4.3 确认执行
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/actions/act_xxx/confirm"
预期：

HTTP 200
ok: true
result.status 为 executed 或 failed（至少有明确结果）
4.4 拒绝执行（可另测一次）
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/actions/act_xxx/reject"
预期：

HTTP 200
result.status: rejected
5) Week C 统一错误响应验证
5.1 参数校验错误（422）
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"\"}"
预期：

HTTP 422
返回结构含：ok=false, error_code=MM422_VALIDATION_ERROR
5.2 动作不存在（404）
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/actions/not_exist/reject"
预期：

HTTP 404
error_code=MM404_ACTION_NOT_FOUND
6) Week D 鉴权验证
先改 .env：

API_AUTH_ENABLED=true
API_AUTH_KEY=your_test_key_123
然后重启 uvicorn。

6.1 不带 key 请求
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"hello\"}"
预期：

HTTP 401
error_code=MM401_UNAUTHORIZED
6.2 带正确 key 请求
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: your_test_key_123" ^
  -d "{\"message\":\"hello\"}"
预期：

HTTP 200，正常返回
7) Week D 限流验证
.env 改成低阈值便于压测：

API_RATE_LIMIT_PER_MIN=2
重启服务，且 API_AUTH_ENABLED=true 时记得带 key。

连续快速发 3 次：

curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" -H "Content-Type: application/json" -H "X-API-Key: your_test_key_123" -d "{\"message\":\"r1\"}"
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" -H "Content-Type: application/json" -H "X-API-Key: your_test_key_123" -d "{\"message\":\"r2\"}"
curl.exe -X POST "http://127.0.0.1:8001/v1/sessions/demo/chat" -H "Content-Type: application/json" -H "X-API-Key: your_test_key_123" -d "{\"message\":\"r3\"}"
预期：

前两次大概率 200
第三次 429，error_code=MM429_RATE_LIMITED
响应头有 Retry-After
8) 响应头与追踪验证（D阶段）
任意 /v1/* 请求，检查响应头是否包含：

X-Request-Id
X-Process-Time-Ms
X-RateLimit-Limit
X-RateLimit-Remaining
9) 最终验收清单（你逐条勾选）

 healthz/readyz 正常

 /chat 正常返回 answer

 /state 包含动作队列与执行日志

 /stream 能持续收到事件并以 run_completed 结束

 confirm/reject 能更新动作状态

 422/404 错误码统一

 鉴权开关生效（401/200符合预期）

 限流生效（429 + Retry-After）

 关键响应头齐全（request-id/耗时/限流头）
你现在先从 第1步 开始。
执行后把结果贴我（成功/失败 + 返回内容），我按你的实测结果继续带你逐项确认