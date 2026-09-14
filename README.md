## 文档导航（建议先看）

- 项目架构图：`architecture_diagram.md`
- FastAPI 说明：`app/README.md`
- MCP 接入：`mcp_quickstart.md`
- Harness 回归：`harness/README.md`
- FastAPI 周计划记录：`fastapi_weekA.md`
- 日更统一入口：`get_data/daily_paper_or_news_multiModual/README.md`
- 多模态子Agent：`agent/multiModal_agent/README.md`
- Dify 定时触发：`dify_scheduler_guide.md`

## 密钥安全推荐方案（先记录，暂不改代码）

推荐方案（最实用）：系统环境变量存密钥 + `.env` 只放非敏感配置。

- 优点：不在文件里明文落地密钥、改造成本最低、与当前代码兼容。
- 原则：`.env` 中密钥字段留空，程序优先从系统环境变量读取真实值。

### Windows（PowerShell）设置示例

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "你的_deepseek_key", "User")
[Environment]::SetEnvironmentVariable("DIFY_APP_API_KEY", "你的_dify_app_key", "User")
[Environment]::SetEnvironmentVariable("DIFY_DATASET_API_KEY", "你的_dify_dataset_key", "User")
[Environment]::SetEnvironmentVariable("VISION_API_KEY", "你的_vision_key", "User")
[Environment]::SetEnvironmentVariable("VOICE_ASR_API_KEY", "你的_asr_key", "User")
[Environment]::SetEnvironmentVariable("VOICE_TTS_API_KEY", "你的_tts_key", "User")
```

### `.env` 处理建议

- 保留非敏感项（开关、URL、超时、模型名、路径等）。
- 敏感项（各类 `*_API_KEY`）留空，不写真实值。
- 修改后重启终端/IDE，使新环境变量生效。

### 验证方式（不输出明文）

```powershell
$k = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY","User")
if ([string]::IsNullOrWhiteSpace($k)) { "DEEPSEEK_API_KEY 未设置" } else { "DEEPSEEK_API_KEY 已设置，长度=$($k.Length)" }
```

你的项目现状（基线）
你现在已经有一套不错的 Agent 内核：

编排层：graph.py（intent_router -> executor -> tools -> synthesizer -> critic）
认知层：nodes.py（意图识别、执行、总结、审查、重试）
能力层：tools.py（Dify 检索 + Web 搜索）
记忆层：SQLite checkpoint（会话延续）
交互层：main_web.py + main_cli.py
配置层：config.py（已集中化）
一句话定位：你已完成“贾维斯大脑”的雏形，但还缺“耳朵、嘴巴、眼睛、手臂、安全系统”。

8 周路线图（按周可交付）
第 1 周：稳定内核（让系统可持续迭代）
目标：先把可靠性打牢。
做什么：

增加统一日志上下文（thread_id / task_id / node_name / retry_count）
给 tools.py 增加超时、重试、错误码归一化
增加基础健康检查命令（模型连通性、Dify 可达性、DB 可写）
改动重点：config.py、tools.py、main_cli.py
验收：连续 20 次问答不崩，异常可定位到具体节点。

第 2 周：任务化执行（从聊天到办事）
目标：支持“一个请求 -> 多步骤任务”。
做什么：

在状态里增加 task_plan / current_step / step_status
新增 Planner 节点（先拆任务再执行）
Executor 按步骤推进并回写状态
改动重点：state.py、nodes.py、graph.py
验收：能完成“检索 -> 汇总 -> 输出参考文献”三步链路，并显示每步状态。

第 3 周：证据化回答（可追溯，抗幻觉）
目标：回答必须带证据来源。
做什么：

工具结果统一附 source_id/source_type/timestamp
Synthesizer 输出中强制“结论 + 证据段 + 不确定项”
Critic 新增“证据覆盖率”审查规则
改动重点：tools.py、nodes.py
验收：每次回答至少含 2 条可追溯来源；无来源内容明确标记“暂无公开信息”。

第 4 周：语音第一版（耳朵和嘴巴）
目标：完成语音对话闭环。
做什么：

接入 ASR（语音转文本）和 TTS（文本转语音）
支持“按键说话”或“短句自动结束”
Web 端显示文本与语音同步状态
建议新增：voice/ 模块（asr.py、tts.py）
验收：可语音提问并语音回复，端到端延迟可接受（先能用，再优化）。

第 5 周：视觉第一版（眼睛）
目标：让助手能看图、看截图、看文档页。
做什么：

Web 端支持上传图片/截图
新增视觉工具（图片理解、图表摘要、OCR 提取）
多模态上下文并入 Synthesizer（文本 + 图像结论）
建议新增：vision/ 模块
验收：用户上传论文图表截图，系统能解释图中核心结论并给出文本综述。

第 6 周：行动能力（手）
目标：从“建议”变成“执行”。
做什么：

增加 Action 工具层（邮件、日历、文件、脚本执行）
引入风险分级：低风险自动执行，中高风险确认
全量动作审计日志（谁、何时、做了什么）
建议新增：actions/ 模块、audit.log
验收：能执行“生成综述并保存文件/发送邮件草稿”，高风险动作会二次确认。

第 7 周：长期记忆与个性化（人格）
目标：让它越来越懂你。
做什么：

增加用户画像记忆：偏好风格、常用关键词、常见任务模板
区分短期会话记忆与长期偏好记忆
增加“记忆写入策略”（只记录高价值信息）
建议新增：memory/ 模块
验收：同类任务第二次执行更快、更贴合你的输出偏好。

第 8 周：贾维斯 MVP 封版（可演示）
目标：形成一个可展示、可复现的版本。
做什么：

统一 Web 面板：任务计划、执行进度、证据、动作日志、审查结果
制作 3 条演示脚本（科研助手、办公助手、多模态分析）
跑一轮回归测试与性能基线
验收：对外可演示 10 分钟，三条场景稳定跑通。

贾维斯 MVP 的“定义标准”（你可以贴墙上）
满足以下 6 条就算成功：

能语音对话（听 + 说）
能看图并融合到回答
能调用外部工具完成任务
能自我审查并纠错
能记住用户偏好并复用
能安全执行动作且可审计
技术栈建议（尽量少折腾）
编排：继续 LangGraph（你已有）
模型：保持 DeepSeek 双模型策略（路由快、总结强）
语音：Whisper 类 ASR + 低延迟 TTS
视觉：先接统一 VLM 接口，后续可替换模型
存储：SQLite（开发）-> Postgres（上线）
观测：结构化日志 + 回放数据集

第 8 周交付物（当前仓库）
- 演示脚本：`demo_scripts_week8.md`
- 10分钟演示流程：`demo_runbook_week8_10min.md`
- 回归与性能基线：`regression_baseline_week8.md`
- MVP 回放集：`task_replay_samples.md`
- 封版检查清单：`mvp_release_checklist_week8.md`
- 项目架构图：`architecture_diagram.md`
- 重构说明：`refactor_notes_week8.md`
- FastAPI Week A：`fastapi_weekA.md`
- MCP 快速开始：`mcp_quickstart.md`
- Harness 使用说明：`harness/README.md`




flowchart TD
    U[用户]
    CLI[main_cli.py]
    WEB[main_web.py<br/>Streamlit UI]
    G[graph.py<br/>create_agent_app()]
    S[state.py<br/>AgentState]
    LOG[runtime_context.py<br/>结构化日志]

    subgraph LangGraph工作流
      IR[intent_router]
      PL[planner]
      EX[executor]
      TL[tools]
      SY[synthesizer]
      CR[critic]
    end

    subgraph 工具层 tools.py
      DIFY[search_dify_arxiv_db]
      NEWS[search_web_news]
      ACT1[action_write_report_file]
      ACT2[action_create_email_draft]
      ACT3[action_run_shell_command]
    end

    subgraph 动作子系统 actions/
      AP[policy.py<br/>风险分级]
      AH[handlers.py<br/>确认后执行]
      AA[audit.py<br/>审计日志]
    end

    subgraph 多模态与记忆
      VO[voice/<br/>ASR/TTS]
      VI[vision/<br/>图片解析 OCR/Chart]
      MEM[memory/<br/>profile+high value+retriever]
      WTR[web_task_runtime.py<br/>任务看板状态]
    end

    DB[(SQLite Checkpoint<br/>AGENT_DB_PATH)]
    AUDIT[(audit.log)]
    PROFILE[(user_profiles.json)]

    U --> CLI
    U --> WEB

    WEB --> VO
    WEB --> VI
    WEB --> MEM
    WEB --> WTR
    WEB --> G
    CLI --> G

    G --> IR --> PL --> EX
    EX -->|需要工具| TL --> EX
    EX -->|无需工具| SY --> CR
    CR -->|REJECT| EX
    CR -->|ACCEPT| OUT[最终回答]

    TL --> DIFY
    TL --> NEWS
    TL --> ACT1
    TL --> ACT2
    TL --> ACT3

    ACT1 --> AP
    ACT2 --> AP
    ACT3 --> AP
    ACT1 --> AH
    ACT2 --> AH
    ACT3 --> AH
    ACT1 --> AA
    ACT2 --> AA
    ACT3 --> AA

    AA --> AUDIT
    MEM --> PROFILE
    G --> DB

    S -.共享状态.-> IR
    S -.共享状态.-> PL
    S -.共享状态.-> EX
    S -.共享状态.-> SY
    S -.共享状态.-> CR

    IR --> LOG
    PL --> LOG
    EX --> LOG
    SY --> LOG
    CR --> LOG
    TL --> LOG
