# Week8 回归与性能基线

## 一、功能回归清单
- [ ] 文本问答链路可跑通（intent -> planner -> executor -> synthesizer -> critic）
- [ ] 证据引用规则生效（`[E#]/[V#]/[A#]`）
- [ ] 语音输入/语音播报（开启配置后）
- [ ] 图片上传、OCR/图表摘要、融合回答
- [ ] 动作工具分级执行（low自动、medium/high确认）
- [ ] 动作审计日志可查看、可筛选
- [ ] 用户偏好记忆可保存、自动学习可生效
- [ ] 长期记忆相关召回可生效（非全量注入）

## 二、建议回归命令
- `python -m compileall config.py state.py graph.py main_web.py node tools memory actions vision`
- `python -m unittest tests.test_runtime_helpers tests.test_voice_pipeline tests.test_vision_pipeline tests.test_actions_runtime tests.test_memory_profile tests.test_memory_learner tests.test_memory_high_value tests.test_memory_retriever`

## 三、性能基线（手工记录）
- 首 token 延迟（文本问答）：____ 秒
- 完整回答时延（文本问答）：____ 秒
- 图片解析时延（Vision）：____ 秒
- 动作确认后执行时延：____ 秒
- 端到端语音问答时延：____ 秒

## 四、最低验收阈值（建议）
- 文本问答完整时延：P50 < 12s
- 图片解析（单图）：P50 < 15s
- 动作确认后执行：P50 < 5s（文件/草稿动作）
- 证据覆盖率：有证据场景下 > 0
- 严重错误率（崩溃/中断）：< 5%
