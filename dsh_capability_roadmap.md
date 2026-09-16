# 引入 dsh 后的能力边界与升级路线

配套文档：[`dsh_hybrid_plan.md`](dsh_hybrid_plan.md)（原计划）、[`dsh_hybrid_plan_review.md`](dsh_hybrid_plan_review.md)（评审与前置修正）。

本文回答两个问题：按混合方案接入 dsh 之后，**哪些能力在 dsh 侧可用、哪些仍是 Python 独有**；以及在此边界之上，**后续升级应该按什么顺序做**。判断依据是当前代码（`node/`、`skills/`、`memory/`、`vision/`、`app/service/agent_runner.py`）与 dsh 官方文档（skills、subagents、jobs、webhook、attachments、session log）。

---

## 1. 能力边界

混合形态下，dsh 只拿到 6 个 MCP 工具：`healthz`、`research_search`、`get_state`、`action_request_*`、`confirm_action`、`reject_action`。边界由这 6 个工具划定。

### 1.1 dsh 侧能做的

- 用 dsh 自己的模型对话，自主决定何时调 `mcp__mmagent__research_search`，拿到 Dify 知识库 / DuckDuckGo 的**原始检索结果**后自行组织答案。
- 发起三类动作（写文件、邮件草稿、shell）并排队等确认；用户在对话里说「确认」，模型再调 `confirm_action`。
- dsh 原生能力全部可用：append-only 会话日志（resume / fork / replay / Trajectory 视图）、SKILL.md 技能、subagent、jobs、goals、web 检索。这些是项目当前没有的。

### 1.2 dsh 侧碰不到的（仍是 Python 独有）

| 能力 | 现状 | 为什么 dsh 拿不到 |
|---|---|---|
| **质量门**：intent → planner → executor → synthesizer → critic；`[E#]/[V#]/[A#]` 证据引用；覆盖率为 0 直接打回（`node/review.py:229`）；最多 `MAX_CRITIC_RETRIES` 次重试 | 只在 `chat` 路径里 | `chat` 不暴露给 dsh。dsh 拿到 `research_search` 的原始结果后由自己的模型自由发挥，**没有证据引用约束，也没有 critic**。这是最大的一条边界：**dsh 里的对话 ≠ 贾维斯的对话**，答案质量下限不同 |
| 技能路由 | `skills/*.md`，自定义 frontmatter（`name` / `description` / `triggers`），由 `intent_router` 用 LLM 选 | 与 dsh 的 SKILL.md（kebab-case，`name` + `description`）格式不同。dsh 看不到项目技能，项目也看不到 dsh 技能。**两套技能系统并存、互不可见** |
| 视觉 | `vision/analyzer.py`（general / ocr / chart）只挂在 Streamlit | dsh web 有 `ctx.attachments` 能收图，但图片不会流到 Python 的视觉管线 |
| 语音 ASR / TTS | Streamlit 专属 | dsh web 没有语音通道 |
| 长期记忆 | `databank/user_profiles.json`，按 LangGraph `thread_id` 存 profile + memory_notes | 无 MCP 入口；dsh 会话不注入用户偏好 |
| 论文日报 | `run_on_startup.bat` 直跑 `agent/multiModal_agent` | 计划 2.3 的 `paper_run` 做完前不可达 |
| 模型配置 | Python 固定走 `model/settings.py` 的 DeepSeek | dsh 自己一套 provider 配置。两处密钥、两处计费；将来若加 `run_insights_agent`，一次提问是两份模型开销 |

### 1.3 三条隐藏边界

计划里没写，但使用中一定会撞到。

**审批权归属变了。** Streamlit 里确认是一个按钮；dsh 里确认是「模型理解了用户说的'可以'，然后自己调 `confirm_action`」。审批的最后一跳落在模型身上而不是人。对 `action_request_shell_command` 这类 high 风险动作，这个语义弱化不可忽视。

**待确认队列不耐重启。** 即使按评审 3.1 把 MCP 合并进 FastAPI 进程，`AgentRunner._session_store`（`app/service/agent_runner.py:18`）仍是内存 dict。Python 一重启，dsh 会话日志里还留着 `act_xxx`，但 `confirm_action` 会返回 `MM404_ACTION_NOT_FOUND`。dsh 会话是持久的，Python 侧状态不是——**两侧持久化等级不对等**。

**并发上限是 1 个 Python 进程。** dsh 一个 Host 里多个会话共用一个 MCP 子进程（或一个 HTTP 端点）；`AgentRunner` 的锁只包住 store 读写，SQLite 连接是 `check_same_thread=False` 共享的。两个会话同时触发长检索的行为未经验证。

---

## 2. 升级路线

分四层，前一层是后一层的前提。

### 第 1 层：让混合形态站稳

内容见 `dsh_hybrid_plan_review.md` 第 3 节，此处只列清单：

- MCP 挂进 FastAPI 进程（`FastMCP.streamable_http_app()` + lifespan 接 `session_manager.run()`），dsh 切 `streamable-http`
- `session_id` 改为服务端缺省，不由模型填
- 抽 `register_tools(mcp, include=...)`，dsh 只见 6 个工具，去掉 10 个别名
- 统一 `ACTION_AUTO_EXECUTE_MAX_RISK` 在 MCP 路径与 LangGraph 路径上的语义
- `paper_run` 做成 `start` / `status` 两段式
- CI 跑 `pytest tests`

### 第 2 层：补掉三条隐藏边界

**待确认队列落库。** 把 `action_pending_queue` / `action_execution_logs` / `pending_action_results` 从内存 dict 迁到 `AGENT_DB_PATH` 同一个 SQLite 里的独立表。做完后 Streamlit 审批面板、FastAPI、dsh 读的才是真正的同一份数据，且耐重启。这一步比进程合并更根本，可以替代它，也可以叠加。

**审批收回给人。** dsh 的工具管线是 `tools/pre-execute → tools/execute → tools/post-execute` 三段 waterfall，加上独立的 approval 服务（`@deepseek-ai/dsh-user-approval`）。一个很小的 patch 就能把 `mcp__mmagent__confirm_action` 和 `mcp__mmagent__action_request_shell_command` 标成必须走 dsh 的人工 approval（`approval: ask`），让确认重新变成 UI 点击而不是模型决定。不需要改 Python。

**技能桥接（性价比最高的一项）。** 把 `skills/LiteratureReview/skill.md` 这类 SOP 导出成 dsh 格式，放到项目根的 `.dsh/skills/literature-review/SKILL.md`（dsh 的 project 层技能根，发现优先级最高，只扫一层目录），把 SOP 里的「使用检索工具」改写成 `mcp__mmagent__research_search`。dsh 的 `skill` 工具会自己完成路由，SOP 资产在两个入口复用。Python 侧 `intent_router` 保持不动，继续服务 Streamlit。

### 第 3 层：把 Python 独有的能力开放给 dsh

**`run_insights_agent` 返回结构化结果，而不是一段文本。** 把 `evidence_items`、`evidence_cited_ids`、`critic_score`、`evidence_coverage`（这些字段已在 `AgentState` 里）与答案一起返回，dsh 侧就能渲染引用编号，用户在 dsh 里也能拿到带质量门的答案。这是让「dsh 对话 ≈ 贾维斯对话」的唯一途径，且不需要把 critic 迁到 TypeScript。作为**一个**重工具暴露，不是默认对话入口。

**`vision_analyze(image, mode)` MCP 工具**包装 `vision/analyzer.py`。dsh web 已有图片附件通道，加这一个工具就把多模态能力接过去了。语音留在 Streamlit。

**记忆：先定单一事实来源。** 要么加 `memory_get_profile` / `memory_append_note` MCP 工具（按服务端 session id 键），要么接 dsh 官方文档里的 memory MCP 模式。两边各存一份是最差的选择。

**从「开机直跑」升级为「事件驱动」。** dsh 有 `ctx.webhookRuntime`，能由外部 HTTP 投递创建 Workspace Session。可以做成：`multiModal_agent` 跑完 → POST webhook → dsh 自动开一个会话讲解今日日报。这是项目目前没有的**主动推送**能力，也是 `run_on_startup.bat` 与 GitHub Action 定时触发（`.github/workflows/dify_daily_trigger.yml`）的自然归宿。

**回归测试补 dsh 一条腿。** 计划里 dsh → MCP 链路只有「手工冒烟」。dsh 有 `--profile headless` 和 Python SDK，可以加一个 `harness/runners/dsh_runner.py`，把 `harness/` 现有用例集跑一遍 dsh 入口。

**可观测性关联。** HTTP 模式下把 `X-Request-Id`（`app/api/main.py:59` 已生成）透传进 MCP 调用，`runtime_context.log_event` 和 `audit.log` 记同一个 id，dsh 的 session JSONL 里就能反查到 Python 侧日志。

### 第 4 层：留到有数据后再做的决策

**编排层到底放哪。** planner / critic 有两个候选位置：LangGraph（Python）和 dsh 的 `agent/*` 事件（TypeScript 插件）。计划说第一期不迁，这是对的。但要提前定判断标准，否则会长期两套并行：

- 若第 3 层做完后，绝大多数对话走 dsh、Streamlit 真的降成了视觉 / 审批面板，那 LangGraph 的 planner / critic 就只剩 `run_insights_agent` 一个消费者。此时可以把证据规则迁成 dsh 的 `tools/post-execute` 插件，Python 收缩成纯领域工具集。
- 反之若 Streamlit / FastAPI 仍是主入口，LangGraph 留着，dsh 就是一个外挂客户端。

这个判断只能靠上线后的入口流量来做，不要预先决定。

---

## 3. 可选项

**Code Mode。** dsh 支持 `DSH_TOOLS_MODE=code`，模型可以在一步里写脚本连续调多次 `research_search`。对「文献综述拆 3 个关键词分别检索」这类 SOP，比 native 模式少两轮模型往返。适合在第 2 层技能桥接时顺手验证，不作为主线。

---

## 4. 一页总结

| | 现在（混合第一期） | 第 2 层后 | 第 3 层后 |
|---|---|---|---|
| dsh 里的答案质量 | 无证据约束、无 critic | 同左 | 经 `run_insights_agent` 可拿到带 `[E#]` 与 critic 分数的答案 |
| 审批 | 模型调 `confirm_action` | dsh UI 人工 approval | 同左 |
| 待确认队列 | 进程内存，不耐重启，三处不互通 | SQLite 单一份，耐重启 | 同左 |
| 技能 | 两套并存 | SOP 导出到 `.dsh/skills` 复用 | 同左 |
| 视觉 / 记忆 | Streamlit 专属 | 同左 | 经 MCP 工具对 dsh 开放 |
| 论文日报 | 开机直跑 | `paper_run` 两段式 | webhook 事件驱动、主动推送 |
| 回归 | 手工冒烟 | 同左 | headless / SDK 自动跑 |
