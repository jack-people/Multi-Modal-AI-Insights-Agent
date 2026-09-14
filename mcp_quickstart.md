# MCP 快速开始

## 1. 安装依赖

```bash
pip install mcp
```

如果你当前环境没有安装项目已有依赖（如 `fastapi`、`langchain`、`requests`），请先补齐你正在使用的运行环境。

## 2. 启动 MCP Server

```bash
python mcp_server.py
```

## 3. 已暴露的 MCP Tools

- `healthz()`
- `research_search(query, source="auto")`
- `chat(session_id, message, inputs=None)`
- `stream_chat(session_id, message, inputs=None, max_events=200)`
- `get_state(session_id)`
- `action_request_write_file(session_id, filename, content)`
- `action_request_email_draft(session_id, recipient, subject, body)`
- `action_request_shell_command(session_id, command)`
- `confirm_action(session_id, action_id)`
- `reject_action(session_id, action_id)`

分组别名（推荐前端按组接入）：

- `system_healthz()`
- `research_lookup(query, source="auto")`
- `session_chat(...)`
- `session_stream_chat(...)`
- `session_get_state(...)`
- `actions_request_write_file(...)`
- `actions_request_email_draft(...)`
- `actions_request_shell_command(...)`
- `actions_confirm(...)`
- `actions_reject(...)`

## 4. 建议测试顺序

1. `healthz`
2. `research_search`（先验证检索链路）
3. `chat`（例如 `session_id=demo`）
4. `stream_chat`（看节点事件流，或直接用 `session_stream_chat`）
5. `action_request_*`（创建待确认动作）
6. `get_state`（查看 `action_pending_queue` 是否出现 `act_xxx`）
7. 用 `confirm_action` 或 `reject_action` 完成审批闭环

## 4.0 research_search 参数说明

```json
{
  "query": "多模态 Agent 评测",
  "source": "auto"
}
```

- `source="dify"`：只走 Dify 检索
- `source="web"`：只走 Web 检索
- `source="auto"`：优先 Dify，失败时回退 Web

## 4.1 stream_chat 返回结构说明

`stream_chat` 会把流式事件收集成列表返回，适合不支持原生 streaming 的 MCP 客户端：

```json
{
  "ok": true,
  "session_id": "demo",
  "event_count": 8,
  "truncated": false,
  "events": [
    {"type": "run_started", "data": {}},
    {"type": "node_update", "data": {}},
    {"type": "run_completed", "data": {}}
  ]
}
```

- `max_events` 可控上限，防止一次返回过大
- 当达到上限时，`truncated=true`

## 4.2 MCP 动作审批闭环（推荐）

1) 先调用：
- `action_request_write_file` 或
- `action_request_email_draft` 或
- `action_request_shell_command`

2) 记录返回中的 `action_id`

3) 调用 `get_state(session_id)`，确认该 `action_id` 存在于 `action_pending_queue`

4) 调用：
- `confirm_action(session_id, action_id)`（执行）或
- `reject_action(session_id, action_id)`（拒绝）

5) 再次 `get_state`，确认动作从 `action_pending_queue` 消失，并出现在 `action_execution_logs`

## 5. Cursor MCP 配置示例

你可以在 MCP 客户端配置中将该服务注册为 stdio 模式，命令示例：

```json
{
  "mcpServers": {
    "multi-modal-agent": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "d:/A_ZJJ_Project/Multi-Modal AI Insights Agent"
    }
  }
}
```

> 注意：不同客户端的配置文件位置和字段名可能略有差异，但核心是 `command + args + cwd`。
