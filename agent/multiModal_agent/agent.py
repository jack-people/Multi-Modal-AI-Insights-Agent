import json
import re
import time
from datetime import datetime

from .loader import load_multimodal_sources_with_meta
from .log_utils import setup_logger
from .processor import build_stats, prepare_sources
from .schemas import AnalysisReport, SourceItem

logger = setup_logger("multiModal_agent.core")


class MultiModalAnalysisAgent:
    """
    子 Agent（数据处理 -> 初步分析 -> 总结）:
    1) 读取数据源（论文 + 新闻）
    2) 评分与筛选高价值样本
    3) 调用模型生成结构化分析结论
    """

    def collect(self, paper_limit: int = 30, news_limit: int = 30) -> tuple[list[SourceItem], list[str]]:
        logger.info("开始收集数据源: paper_limit=%s, news_limit=%s", paper_limit, news_limit)
        items, warnings = load_multimodal_sources_with_meta(paper_limit=paper_limit, news_limit=news_limit)
        logger.info("数据收集完成: total=%s, warnings=%s", len(items), len(warnings))
        return items, warnings

    def select(self, items: list[SourceItem], top_k: int = 20) -> list[SourceItem]:
        logger.info("开始样本筛选: input=%s, top_k=%s", len(items), top_k)
        selected = prepare_sources(items, keep_top_k=top_k)
        logger.info("样本筛选完成: selected=%s", len(selected))
        return selected

    @staticmethod
    def _extract_json_payload(text: str) -> dict:
        raw = str(text or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

        # 兼容模型返回 ```json ... ``` 或者前后附加解释文本
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S)
        if fence_match:
            candidate = fence_match.group(1)
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start : end + 1]
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _is_context_error(error_text: str) -> bool:
        text = (error_text or "").lower()
        keys = [
            "maximum context length",
            "context length",
            "too many tokens",
            "token limit",
            "context window",
            "prompt is too long",
        ]
        return any(k in text for k in keys)

    @staticmethod
    def _is_timeout_error(error_text: str) -> bool:
        text = (error_text or "").lower()
        keys = ["timeout", "timed out", "read timeout", "504", "gateway timeout"]
        return any(k in text for k in keys)

    @staticmethod
    def _build_evidence_lines(items: list[SourceItem], per_item_chars: int = 900, total_chars: int = 12000) -> list[str]:
        lines: list[str] = []
        used = 0
        for idx, it in enumerate(items, start=1):
            snippet = it.content[:per_item_chars]
            line = (
                f"[S{idx}] type={it.source_type} tags={it.tags} title={it.title}\n"
                f"content={snippet}"
            )
            if used + len(line) > total_chars:
                break
            lines.append(line)
            used += len(line)
        return lines

    def analyze(self, selected_items: list[SourceItem], total_count: int, warnings: list[str] | None = None) -> AnalysisReport:
        warnings = list(warnings or [])
        if not selected_items:
            report = AnalysisReport.empty()
            report.processing_warnings.extend(warnings)
            return report

        stats = build_stats(selected_items)
        refs = [f"[S{idx}] {it.title} ({it.source_type})" for idx, it in enumerate(selected_items, start=1)]
        source_types = {it.source_type for it in selected_items}
        source_hint = "请重点基于论文证据分析。" if source_types == {"paper"} else "请综合论文与新闻证据分析。"

        model_attempts = 0
        model_errors: list[str] = []
        candidate_items = list(selected_items)
        max_attempts = 4

        while model_attempts < max_attempts:
            model_attempts += 1
            logger.info("模型分析尝试: attempt=%s/%s, candidate_items=%s", model_attempts, max_attempts, len(candidate_items))
            evidence_lines = self._build_evidence_lines(candidate_items)
            prompt = f"""你是一个多模态研究情报子Agent。请基于证据做“初步分析总结”。
输出要求：严格输出 JSON 对象，字段如下：
{{
  "executive_summary": "2-4句",
  "key_trends": ["3-6条趋势"],
  "risks": ["2-5条风险"],
  "opportunities": ["2-5条机会"],
  "next_actions": ["3-6条下一步建议"]
}}

额外约束：
1) {source_hint}
2) 避免绝对化措辞，对不确定内容用“可能/需验证”。
3) 输出中文简体。

数据统计：total_selected={len(candidate_items)}, tag_stats={stats}
证据：
{chr(10).join(evidence_lines)}
"""

            try:
                from model import llm_synthesizer
                result = llm_synthesizer.invoke(prompt)
                payload = self._extract_json_payload(result.content)
                if not payload:
                    raise ValueError("模型返回非 JSON 或解析失败")

                report = AnalysisReport(
                    generated_at=datetime.now().isoformat(),
                    total_sources=total_count,
                    selected_sources=len(selected_items),
                    executive_summary=str(payload.get("executive_summary", "")).strip() or "暂无总结。",
                    key_trends=[str(x).strip() for x in payload.get("key_trends", []) if str(x).strip()],
                    risks=[str(x).strip() for x in payload.get("risks", []) if str(x).strip()],
                    opportunities=[str(x).strip() for x in payload.get("opportunities", []) if str(x).strip()],
                    next_actions=[str(x).strip() for x in payload.get("next_actions", []) if str(x).strip()],
                    references=refs,
                    processing_warnings=warnings + model_errors,
                    model_status="ok",
                    model_attempts=model_attempts,
                )
                logger.info("模型分析成功: attempt=%s", model_attempts)
                return report
            except Exception as e:
                err = str(e)
                logger.warning("模型分析失败: attempt=%s, err=%s", model_attempts, err)
                model_errors.append(f"模型第{model_attempts}次调用失败: {err}")
                if self._is_context_error(err) and len(candidate_items) > 3:
                    # 上下文超限时自动减半证据样本重试
                    new_count = max(3, len(candidate_items) // 2)
                    candidate_items = candidate_items[:new_count]
                    logger.warning("触发上下文降载: new_candidate_items=%s", new_count)
                    model_errors.append(f"检测到上下文超限，自动缩减证据到 {new_count} 条后重试。")
                    continue
                if self._is_timeout_error(err) and model_attempts < max_attempts:
                    # 超时短退避重试
                    logger.warning("触发超时重试: sleep=%s", min(model_attempts, 2))
                    time.sleep(min(model_attempts, 2))
                    continue

        # 模型不可用时，返回可用的保底摘要
        logger.error("模型分析进入fallback: attempts=%s", model_attempts)
        top_titles = [it.title for it in selected_items[:5]]
        fallback_risks = ["模型调用失败，结论需人工复核。"]
        if any(it.source_type == "news" for it in selected_items):
            fallback_risks.append("新闻源可能为空，需补齐网络抓取。")
        fallback_actions = ["检查模型密钥与网络连通性。", "重新运行并观察重试日志。", "将结果推送到前端/知识库。"]
        if any(it.source_type == "news" for it in selected_items):
            fallback_actions.insert(1, "补跑 news 抓取并重试分析。")
        return AnalysisReport(
            generated_at=datetime.now().isoformat(),
            total_sources=total_count,
            selected_sources=len(selected_items),
            executive_summary="已完成数据处理与筛选，当前为模型不可用时的保底摘要。",
            key_trends=[f"高频主题：{k}" for k in list(stats.keys())[:5]],
            risks=fallback_risks,
            opportunities=["可接入定时任务生成日报。", "可扩展为专题追踪子Agent。"],
            next_actions=fallback_actions,
            references=[f"[S{i+1}] {t}" for i, t in enumerate(top_titles)],
            processing_warnings=warnings + model_errors,
            model_status="fallback",
            model_attempts=model_attempts,
        )

    def run(
        self,
        paper_limit: int = 30,
        news_limit: int = 30,
        top_k: int = 20,
    ) -> AnalysisReport:
        logger.info("子Agent运行开始")
        all_items, warnings = self.collect(paper_limit=paper_limit, news_limit=news_limit)
        selected = self.select(all_items, top_k=top_k)
        report = self.analyze(selected, total_count=len(all_items), warnings=warnings)
        logger.info("子Agent运行结束: model_status=%s", report.model_status)
        return report
