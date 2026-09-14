# MultiModal 子 Agent

目录：`agent/multiModal_agent`

## 架构建议（已按此落地）

采用“管道式子Agent（Pipeline Agent）”：

1. `loader.py`：多源数据读取（论文/新闻）
2. `processor.py`：标准化、打分、筛选高价值样本
3. `agent.py`：编排处理流程并调用模型做初步分析
4. `run.py`：CLI 入口，产出结构化 JSON 报告

这种结构适合你后续“多个 agent 并存”的目标：每个 agent 保持同模板，不同业务只替换 loader/processor/提示词。

## 与 LangChain 的关系

- 编排层：不是 LangChain 的 AgentExecutor，而是项目内自定义 Pipeline。
- 模型层：使用 LangChain 的 `ChatOpenAI` 客户端（见 `model/clients.py`）。

## 鲁棒性设计（已实现）

- 数据层容错：论文/新闻读取失败会记录 `processing_warnings`，不阻断整体运行。
- 模型超时处理：模型调用失败会自动重试（并保留失败记录）。
- 上下文超限处理：识别 token/context 报错后自动缩减证据样本再重试。
- 输出容错：模型返回非纯 JSON 时，尝试从代码块/文本中提取 JSON；失败则降级为保底摘要。

## 运行

```bash
python -m agent.multiModal_agent.run --paper-limit 30 --news-limit 30 --top-k 20
```

论文优先（默认行为，按 `.env` 每次抓取 10 篇并去重）：

```bash
python -m agent.multiModal_agent.run
```

默认输出：

`output/multiModal_agent/multimodal_initial_report_YYYYMMDD_HHMMSS.json`

可选参数：

- `--output-dir`：指定自动命名输出目录（默认 `output/multiModal_agent`）
- `--output`：指定完整输出文件路径（传入后不使用自动命名）
- `--fail-on-fallback`：模型进入 fallback 时返回非 0 退出码

## 调试日志控制

- `DEBUG_LOG_ENABLED=true` 时输出步骤级日志（收集、筛选、模型重试、fallback 等）
- `DEBUG_LOG_ENABLED=false` 时仅保留最小控制台输出
- 可选：`AGENT_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR` 更细粒度控制日志级别

## 论文自动抓取相关环境变量

- `PAPER_AUTO_FETCH_ON_RUN=true`：每次运行自动拉取最新论文
- `PAPER_FETCH_LIMIT_PER_RUN=10`：每次拉取论文数量（去重后）
- `PAPER_FETCH_LOOP_COUNT=10`：抓取轮数（达到后停止）
- `PAPER_FETCH_INTERVAL_MINUTES=30`：每轮抓取间隔分钟数
- `PAPER_FETCH_QUERY=...`：arXiv 检索查询
- `PAPER_DOWNLOAD_PDF_ON_RUN=true`：抓取后自动下载 PDF 到 `databank/paper_data/01_raw_pdfs`
- `PAPER_PDF_DOWNLOAD_TIMEOUT_SEC=30`：单篇 PDF 下载超时（秒）
- `PAPER_PDF_DOWNLOAD_RETRIES=2`：单篇 PDF 下载重试次数
- `PAPER_ONLY_USE_LATEST_BATCH=true`：仅用本次/最近批次论文做分析
- `MULTIMODAL_AGENT_NEWS_LIMIT=0`：默认不纳入新闻

## 输出字段

- `executive_summary`: 执行摘要
- `key_trends`: 关键趋势
- `risks`: 风险点
- `opportunities`: 机会点
- `next_actions`: 下一步建议
- `references`: 证据索引
