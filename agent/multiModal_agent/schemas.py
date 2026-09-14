from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceItem:
    source_type: str
    title: str
    content: str
    source_path: str
    published_at: str = ""
    score: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    generated_at: str
    total_sources: int
    selected_sources: int
    executive_summary: str
    key_trends: list[str]
    risks: list[str]
    opportunities: list[str]
    next_actions: list[str]
    references: list[str]
    processing_warnings: list[str] = field(default_factory=list)
    model_status: str = "ok"
    model_attempts: int = 0

    @staticmethod
    def empty() -> "AnalysisReport":
        return AnalysisReport(
            generated_at=datetime.now().isoformat(),
            total_sources=0,
            selected_sources=0,
            executive_summary="暂无可用数据，无法生成分析。",
            key_trends=[],
            risks=[],
            opportunities=[],
            next_actions=[],
            references=[],
            processing_warnings=["未读取到任何可分析的数据源。"],
            model_status="empty",
            model_attempts=0,
        )
