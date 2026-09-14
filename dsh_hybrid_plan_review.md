# dsh_hybrid_plan.md 评审

对 `dsh_hybrid_plan.md` 的可行性判断与优化建议。结论基于**实际读代码 + 本机跑验证**，不是纸面推演；下文凡带文件行号的都已实测确认。

**总判断：方案可行，架构切分是对的，但不能按现在的顺序执行。** 有 3 个前置阻塞（其中 2 个已在本分支修掉），4 处与代码/官方文档不符的事实性偏差，以及 1 个应当从「可选/以后」提到第一期的关键调整。

---

## 0. 计划里判断正确、建议原样保留的部分

这几条是整个方案的价值所在，不要在后续修订中被稀释：

- **不整仓替换，dsh 只当对话/路由层。** 正确。
- **不把 `chat`/`stream_chat` 暴露给 dsh。** 正确，而且理由比原文写的更强：`McpService.chat()` 会走完整的 `AgentRunner.run_chat` → LangGraph（intent → planner → executor → synthesizer → critic，critic REJECT 还会回退重跑 executor）。dsh loop 套这一整套，等于一次提问跑两套 agent 循环，token 和延迟都不可控。
- **动作走现有 `action_request_* → confirm_action` 闭环，不开 dsh 的 Code/Shell 去干同样的事。** 正确。
- **`toolCallTimeoutMs` 要显式抬高。** 正确，默认 60s 确实不够。
- **`insert:` 的写法。** 与官方文档一致：用户 patch 层里顶层 `- id: xxx` 是「按 id 替换已有行」，插新行必须包在 `- insert:` 下。写 `- id: mcp-mmagent` 会去匹配一个不存在的行。

---

## 1. 前置阻塞：不先修，2.1「先不改 Python」根本走不到

### 1.1 `config.py` 里 `_env_float` 未定义（已修，本分支 commit 1）

`config.py:52` 调用 `_env_float`，但该函数只定义在 `model/settings.py`，`config.py` 顶部也没从 `model` 导入它。结果是 `import config` 直接 `NameError`：

```
File "/workspace/config.py", line 52, in <module>
    TOOL_RETRY_BACKOFF = _env_float("TOOL_RETRY_BACKOFF", 1.0)
NameError: name '_env_float' is not defined
```

`config` 是 `tools.py` / `graph.py` / `mcp_server.py` / `app/api/main.py` / `main_web.py` / `main_cli.py` 的共同依赖，所以**当前仓库里没有任何一个入口能启动**。dsh 那边只会看到「MCP 子进程起不来」，配上计划里的 `failOnStartupError: true` 就是插件激活被拒，很难反查到是这一行。

已按 `_env_int`/`_env_bool` 的写法补上，补完 `pytest tests` 38 passed。

### 1.2 `requirements.txt` 缺依赖且未约束版本（已修，本分支 commit 2）

按 `requirements.txt` 全新装一遍，`import mcp_server` 会连续撞三个错：

| 缺什么 | 症状 |
|---|---|
| `mcp` 未限版本 | 装到 `mcp 2.x`，`FastMCP` 已改名 `MCPServer`，`mcp_server.py:25` 抛 `ModuleNotFoundError`，被 except 包成 `RuntimeError: 缺少 mcp 依赖` —— 报错信息误导性很强 |
| `langchain-community` | `tools.py:6` 顶层 import，直接 `ModuleNotFoundError` |
| `langgraph-checkpoint-sqlite` | `graph.py:6` 的 `SqliteSaver` 不在 `langgraph` 主包依赖里 |
| `ddgs` | `DuckDuckGoSearchResults` 的运行期后端。注意 `tools.py:270` 的实例化在 `try` **外面**，缺包时 `search_web_news` 直接抛异常，`research_search(source="web")` 也跟着抛 —— 你的**验收标准 1 的 web 分支会挂** |

已补齐，并把 `mcp` 钉到 `<2`。

### 1.3 `model/clients.py` 在 import 期就构造 LLM 客户端（未修，需你决策）

`import config` → `from model import ...` → `model/clients.py` 立即实例化 `ChatOpenAI`，缺 `DEEPSEEK_API_KEY` 时 import 阶段就报 `openai.OpenAIError: Missing credentials`。

这条单独拿出来说，是因为它和 dsh 的环境变量剔除（见 2.2）叠在一起，会变成「patch.yml 写对了但插件就是起不来」的组合故障。要么把客户端改成懒加载，要么在 2.1 之前先手动跑一次 `python mcp_server.py` 确认能起来。

---

## 2. 事实性偏差：4 处需要改掉的描述

### 2.1 「两套会话，靠 `session_id` 对齐 Python 侧 SQLite checkpoint」—— 不成立

这是计划里影响最大的一处误判。**待确认动作队列不在 SQLite 里。**

- 它在 `AgentRunner._session_store`（`app/service/agent_runner.py:18`），是**纯进程内内存 dict**。
- `AGENT_DB_PATH` 的 SQLite 只是 LangGraph 的 `SqliteSaver` checkpoint，存的是消息与图状态，不含 `action_pending_queue`。

于是现在实际存在**三份互不可见的待审批队列**：

| 进程 | 队列位置 |
|---|---|
| `mcp_server.py` | 模块级 `McpService(runner=AgentRunner())`（`mcp_server.py:34`）自己的内存 |
| FastAPI | `app/api/deps.py` 的 `@lru_cache get_agent_runner()`，该进程自己的内存 |
| Streamlit | `st.session_state.action_pending_queue`（`main_web.py:134`），浏览器会话级 |

**传同一个 `session_id` 不会让它们互通**，跨进程唯一共享的东西是 `audit.log`。

直接推论：计划表格里「Streamlit 可逐步降为面板（视觉、**动作审批**）」在当前架构下做不到 —— Streamlit 面板看不见 dsh 经 MCP 发起的动作，点不了确认。这句要么删掉，要么按 3.1 合并进程之后再写。

### 2.2 「dsh 会清环境变量再 spawn 子进程」—— 说法过强，而且这里根本不需要转发密钥

官方原文是：stdio 桥**只**剔除「名字看起来像凭据的变量」和所有 `DSH_*`，其余 ambient 变量照常继承。所以 `DEEPSEEK_API_KEY`/`DIFY_*_API_KEY`/`VISION_API_KEY` 会被剔除，但 `AGENT_DB_PATH`、`DIFY_BASE_URL` 这类不会。

更关键的是：`config.py:9` 已经 `load_dotenv()`。只要 patch.yml 里的 `cwd` 指到项目根目录，`.env` 就会被读到。所以计划里那段

```yaml
env:
  DEEPSEEK_API_KEY: !!js process.env.DEEPSEEK_API_KEY
```

**不需要，而且更脆**：它要求启动 dsh 的那个 shell 里也有这个变量，否则求值成 `undefined`；同时把密钥来源分裂到 `.env` 和 patch.yml 两处。建议直接写 `env: {}`，密钥只留在 `.env` 里。

### 2.3 「dsh 自带文件/Shell，必须关掉」—— `dsh web` 下已经默认关了，要控的是别的东西

`dsh-web-app` bundle 自己就把 `tool-bash`、`tool-pwsh`、`tool-jobs`、`tool-fs`、`tool-fs-search`、`tool-str-replace-editor` 全部 `disabled: true`，改成每个 session 挂 preset 来决定能力集。

所以真正需要盯的是 **session preset 和 `DSH_PERMISSION_MODE`**（默认 `workspace-write` + `approval: ask`，`danger-full-access` 会把 approval 降成 `never`），不是 host 层那几行 `tool-*`。按原文去「关掉 host 行」会得到虚假的安全感：host 行本来就是关的，而 session preset 才是实际放行文件写入的地方。

### 2.4 Node 版本

原文写 Node 22+，官方示例要求的是 22.18+。建议写死 22.18+，省一轮环境排查。

---

## 3. 可优化项（按收益排序）

### 3.1 把 2.4 提到第一期，并且不要另起 HTTP 进程，而是把 MCP 挂进现有 FastAPI 进程

这是最值得改的一条。已实测 `mcp.server.fastmcp.FastMCP` 有 `streamable_http_app()` 和 `session_manager`，默认挂载路径 `/mcp`，所以三步就能做到：

1. `McpService` 的 runner 从 `AgentRunner()` 换成 `app.api.deps.get_agent_runner()`（复用 FastAPI 那一个实例）
2. `create_api_app()` 里 `app.mount("/v1/mcp", mcp.streamable_http_app())`，并把 `mcp.session_manager.run()` 接进 app 的 lifespan
3. dsh 侧改 `transport: streamable-http` + `url: http://127.0.0.1:8000/v1/mcp` + `headers: {X-API-Key: ...}`

一次解决四个问题：

- **待审批队列变成全局唯一的一份**，Streamlit / FastAPI / dsh 看同一个 `action_pending_queue`。2.1 里那个「三份队列」的坑消失，你表格里「Streamlit 降为审批面板」才真的成立。
- **不再每次 spawn Python**。现在 stdio 模式下 dsh 每次拉起子进程都要重新 `create_agent_app()`（装 LangGraph + 连 SQLite + 建 LLM 客户端），是秒级冷启动。
- **密钥/环境变量剔除问题整体消失**（2.2 不用再讨论）。
- **顺带复用 `/v1/` 前缀上已有的鉴权与限流中间件**（`app/api/main.py:71`），dsh 用 `headers` 传 `X-API-Key` 就行。

唯一实现坑：**必须把 `session_manager.run()` 接到 lifespan**，否则第一次 MCP 请求会报 task group 未初始化。代价是 dsh 不再托管 Python 生命周期，你要自己保证 `:8000` 在跑 —— dsh 的 `reconnect` 默认开启，掉线会自动重连并重新同步工具。

### 3.2 不要让模型来填 `session_id`

MCP 协议里没有「会话身份」这个概念，dsh 不会把它自己的 session id 注入工具参数。计划里「dsh 每次调用带同一个 `session_id`（例如 `dsh-<dsh会话id>`）」实际上是**指望模型每轮都编出同一个字符串**，它第二轮换一个，`get_state`、`confirm_action` 就全部对不上，而且失败形式是「动作凭空消失」，很难查。

建议：给 dsh 的那份 MCP 把 `session_id` 改成可选参数，缺省取服务端值（stdio 下读 `MM_MCP_DEFAULT_SESSION_ID`；HTTP 下取 MCP session id 或 `X-Session-Id` 头）。会话对齐由配置保证，不依赖模型自觉。

### 3.3 「收窄 MCP 表面」要连别名一起砍，而且不要复制出第二个文件

实测 `mcp_server.py` 注册了 **20 个工具**，其中 10 个是纯别名（`system_healthz`、`research_lookup`、`session_chat`、`actions_confirm`、`actions_request_*`…）。给 dsh 的那份应该只有 6 个：`healthz`、`research_search`、`get_state`、`action_request_*`、`confirm_action`、`reject_action`。别名对模型只是同义干扰项 —— 两个名字功能相同，选择噪声和 prompt 占用都是白付的。

实现上别按原文新建一个 `mcp_server_dsh.py` 粘贴一遍：`harness/runners/mcp_runner.py` 是 `import mcp_server` 后直接调模块函数的，复制会让两份定义随时间漂移。抽成 `register_tools(mcp, include=[...])`，两个入口共用同一份注册逻辑。

### 3.4 审批语义在两条路径上不一致，加 `run_insights_agent` 之前必须统一

- MCP 路径：`McpService.action_request_write_file` → `AgentRunner.request_action` → `_enqueue_pending_action`，**无条件入队等确认**。已实测：调用后 `get_state` 里出现 `act_xxx`，文件没落盘。
- LangGraph 路径：`tools.py:304` 的 `action_write_report_file` 走 `should_auto_execute(risk="low", ACTION_AUTO_EXECUTE_MAX_RISK)`，而 `ACTION_AUTO_EXECUTE_MAX_RISK` 默认就是 `"low"`（`config.py:76`）→ **低风险写文件直接执行，不等确认**。

所以你的验收标准 2 目前之所以成立，仅仅因为第一期没给 dsh 暴露 `chat`。一旦按计划加了 `run_insights_agent` 或 `paper_run`（内部会走 LangGraph 或写文件），dsh 一句话就能绕过审批落盘，验收标准 2 自动失效。

修法二选一：给 dsh 的入口把 `ACTION_AUTO_EXECUTE_MAX_RISK` 设成不允许任何自动执行；或在 `run_insights_agent` 里强制覆盖该策略。

### 3.5 `paper_run` 建议做成两段式，而不是一次长 tool call

`MultiModalAnalysisAgent.run()` = 抓取（PDF 下载）+ 筛选 + 模型分析，而分析里还有最多 4 次重试（`agent/multiModal_agent/agent.py:117`，含上下文降载和超时退避）。包成一个同步 MCP 工具，就得把 `toolCallTimeoutMs` 抬到 10 分钟，并且 dsh 一旦超时或重连，已经跑了一半的抓取就白费。

建议 `paper_run_start()` 立即返回 `job_id`，`paper_run_status(job_id)` 轮询。超时窗口回到秒级，dsh 侧断线也不丢进度。

### 3.6 验收标准补两条

1. **CI 跑 `pytest tests`。** 现在 `.github/workflows/` 只有 `dify_daily_trigger.yml`，没有任何测试或 import 检查 —— 这就是 1.1 那种 import 期错误能一路带到 main 的原因。仓库里 38 个测试是能过的，只是没人跑。
2. **dsh 侧一次工具调用要能在 Python 日志 / `audit.log` 里定位到同一次调用。** 现在 dsh 事件日志和 Python 侧没有共同关联 id，出问题只能靠时间戳猜。走 3.1 的 HTTP 方案后可以直接复用现成的 `X-Request-Id`（`app/api/main.py:59`）。

---

## 4. 建议的执行顺序（替换原文「先 2.1–2.2 再 2.3–2.4」）

| 步骤 | 内容 | 目的 |
|---|---|---|
| 0 | `config.py` + `requirements.txt`（本分支已做）；CI 加 `pytest tests`；决定 1.3 怎么处理 | 让 Python 侧能启动，否则后面每一步的失败都无法归因 |
| 1 | 2.1 用 stdio 跑通一次，`env: {}` 靠 `.env` | 只为验证 dsh ↔ MCP 通路，不做长期形态 |
| 2 | 2.2 抽 `register_tools(include=...)`，dsh 只见 6 个工具；`session_id` 服务端缺省（3.2、3.3） | 把「一次提问跑两套 loop」和「会话对不上」两个风险堵死 |
| 3 | **提前做 2.4**：MCP 挂进 FastAPI 进程，dsh 切 streamable-http（3.1） | 拿到唯一队列 + 去掉冷启动；到这一步才能谈「Streamlit 降为审批面板」 |
| 4 | 统一审批策略（3.4） | 让验收标准 2 在加新工具后依然成立 |
| 5 | 2.3 的 `paper_run`，两段式（3.5） | 最后做，风险最低 |

原文「先做 2.1–2.2 验证混合是否值得继续」这个思路本身没问题；只是判断「值不值得」的那次验证，如果跑在 stdio + 三份独立队列的形态上，得到的体验会明显差于这套方案真正能达到的水平，容易做出错误的否决。
