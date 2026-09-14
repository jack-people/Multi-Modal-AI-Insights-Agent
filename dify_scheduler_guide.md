# Dify 每日 8 点自动触发

目标：不依赖本地电脑开机，在云端每天北京时间 08:00 调用 Dify Workflow。

## 已提供内容

- 触发脚本：`scripts/trigger_dify_workflow.py`
- 定时任务模板：`.github/workflows/dify_daily_trigger.yml`

## 工作方式

1. GitHub Actions 每天 08:00（UTC+8）触发。
2. 执行 `scripts/trigger_dify_workflow.py`。
3. 脚本调用 Dify API：`POST /v1/workflows/run`。

## 需要配置的 GitHub Secrets

在仓库 Settings -> Secrets and variables -> Actions 中添加：

- `DIFY_BASE_URL`
  - 例如：`https://api.dify.ai`
  - 自建 Dify 则填你的 Dify 域名
- `DIFY_APP_API_KEY`
  - 工作流 App 的 API Key
- `DIFY_USER_ID`（可选）
  - 例如：`multi-modal-agent-scheduler`
- `DIFY_WORKFLOW_INPUTS_JSON`（可选）
  - 例如：`{"task":"daily_multimodal_report","paper_limit":10,"news_limit":0}`

## 本地手动测试

先在环境变量或 `.env` 中配置好 `DIFY_BASE_URL` 与 `DIFY_APP_API_KEY`，再执行：

```bash
python scripts/trigger_dify_workflow.py
```

## 失败排查

- 401/403：检查 `DIFY_APP_API_KEY`
- 404：检查 `DIFY_BASE_URL` 是否正确（是否包含协议与域名）
- 超时：增大 `DIFY_TRIGGER_TIMEOUT_SEC`，并检查 Dify 工作流耗时节点
- inputs 不生效：检查 `DIFY_WORKFLOW_INPUTS_JSON` 是否是合法 JSON
