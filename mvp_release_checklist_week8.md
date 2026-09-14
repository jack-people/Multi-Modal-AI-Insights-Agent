# Week8 MVP 封版检查清单

## 一、功能封版检查
- [ ] 文本问答主链路稳定（router/planner/executor/synthesizer/critic）
- [ ] 证据链可用（`[E#]`、`[V#]`、`[A#]`）
- [ ] 语音输入输出可用（ASR/TTS）
- [ ] 视觉输入与结构化分析可用（general/ocr/chart）
- [ ] 动作执行分级可用（low 自动，medium/high 确认）
- [ ] 动作审计日志可查看并可筛选
- [ ] 个性化偏好保存/自动学习生效
- [ ] 长期记忆写入与相关召回生效

## 二、演示封版检查
- [ ] `demo_scripts_week8.md` 已逐条演练
- [ ] `demo_runbook_week8_10min.md` 已按时序试跑
- [ ] 三大场景（科研/办公/多模态）可在 10 分钟内跑通

## 三、质量与稳定性
- [ ] `python -m compileall` 通过（核心模块）
- [ ] 关键测试通过（memory/actions/vision/runtime helpers）
- [ ] 无新增 lint 错误
- [ ] 关键失败路径可观测（失败原因、审查反馈、动作状态）

## 四、性能基线记录
- [ ] 文本问答首 token 与完整时延已记录
- [ ] 图片解析时延已记录
- [ ] 动作确认后执行时延已记录
- [ ] 语音端到端时延已记录

## 五、发布前确认
- [ ] `.env` 配置完整且无泄漏敏感信息
- [ ] `README.md` 交付物索引完整
- [ ] 演示账号/会话 ID 已准备
- [ ] 回滚方案与问题定位路径明确
