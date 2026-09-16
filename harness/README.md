# Harness 使用说明

## 目标

在同一套用例下，回归验证 `local / api / mcp` 三种入口能力，输出统一报告：

- `harness/report/latest.json`
- `harness/report/latest.md`

并采用双阶段执行模型：

- `Initializer`：加载 suite、生成执行计划、写入 workspace
- `Executor`：读取计划执行并持续写入结果
- `Workspace`：持久化 run 生命周期与中间状态

## 前置依赖

`harness` 会复用项目运行时依赖，至少需要：

- `pydantic`
- `fastapi`（跑 API 相关 case 时）
- `langchain` / `langchain-core` / `langchain-openai`
- 以及项目现有依赖（`config.py`、`app/service/agent_runner.py` 依赖链）

如果你在精简环境里运行，建议先在项目虚拟环境安装依赖后再执行 harness。

## 快速运行

```bash
python -m harness.run_harness --suite harness/cases/core_10_cases.json
```

推荐门禁套件（更稳定）：

```bash
python -m harness.run_harness --suite harness/cases/ci_gate.json
```

一键运行并打印报告：

```bash
python -m harness.run_and_show --suite harness/cases/ci_gate.json
```

按模式执行并打印报告：

```bash
# run: 初始化并执行（默认）
python -m harness.run_and_show --mode run --suite harness/cases/ci_gate.json

# resume: 继续指定 run_id
python -m harness.run_and_show --mode resume --run-id <run_id>

# exec: 重新执行指定 run_id
python -m harness.run_and_show --mode exec --run-id <run_id>
```

CI 只要结构化输出（不打印 markdown）：

```bash
python -m harness.run_and_show --mode run --suite harness/cases/ci_gate.json --json-only
```

## 双阶段命令（推荐）

初始化：

```bash
python -m harness.cli init --suite harness/cases/ci_gate.json
```

执行：

```bash
python -m harness.cli exec --run-id <run_id>
```

一键 init+exec：

```bash
python -m harness.cli run --suite harness/cases/ci_gate.json
```

恢复运行：

```bash
python -m harness.cli resume --run-id <run_id>
```

如果要指定 API 地址：

```bash
python -m harness.run_harness \
  --suite harness/cases/core_10_cases.json \
  --api-base-url http://127.0.0.1:8001
```

## 用例说明

默认套件：`harness/cases/core_10_cases.json`

门禁套件：`harness/cases/ci_gate.json`

覆盖范围：

- Local：基础聊天 + 动作入队 + confirm
- API：healthz/chat/stream
- MCP：healthz/research_search/动作入队 + reject

`ci_gate` 覆盖范围：

- Local：healthz/chat/state/动作入队+reject
- MCP：healthz/chat/stream/动作入队+confirm
- 默认不依赖外部 API 服务（更适合 CI）

## Workspace 持久层结构

每个 run 会生成目录：`harness/workspace/<run_id>/`

- `manifest.json`：运行元信息
- `plan.json`：执行计划
- `status.json`：运行状态（initialized/running/finished/failed）
- `context.json`：动态上下文（如 `last_action_id`）
- `progress.json`：已完成 case（用于 resume）
- `events.jsonl`：执行事件流
- `results.jsonl`：逐 case 结果
- `report.json` / `report.md`：该 run 的最终报告

## 结果判定

每条 case 通过以下规则断言（可按需扩展）：

- `status_code`
- `ok`
- `contains_keys`
- `error_code`
- `stream_contains`
- `pending_queue_min`
- `action_status_in`
- `max_latency_ms`

## 建议接入 CI

将命令接入 CI：

```bash
python -m harness.run_harness --suite harness/cases/ci_gate.json
```

若存在失败 case，脚本退出码为 `1`，可直接作为门禁。
