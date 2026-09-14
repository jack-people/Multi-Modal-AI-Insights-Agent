"""DEPRECATED: 兼容旧导入路径，请优先使用 `node.common`。"""

from node.common import (
    retry_count,
    get_latest_question,
    parse_tool_message,
    collect_evidence,
    format_evidence_for_prompt,
    extract_cited_evidence_ids,
    build_tool_context,
    build_dialog_context,
)

__all__ = [
    "retry_count",
    "get_latest_question",
    "parse_tool_message",
    "collect_evidence",
    "format_evidence_for_prompt",
    "extract_cited_evidence_ids",
    "build_tool_context",
    "build_dialog_context",
]
