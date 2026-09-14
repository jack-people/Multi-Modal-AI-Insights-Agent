import json
from state import AgentState

MAX_EVIDENCE_SNIPPET = 500


def retry_count(state: AgentState) -> int:
    return int(state.get("retry_count", 0))


def get_latest_question(messages: list) -> str:
    """从后往前提取用户最新真实提问（跳过 Critic 反馈）。"""
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human" and "【Critic 审查未通过】" not in msg.content:
            return msg.content
    return messages[0].content


def parse_tool_message(raw_content: str) -> str:
    """解析统一工具协议，失败时回退为原始文本。"""
    try:
        payload = json.loads(raw_content)
        if not isinstance(payload, dict):
            return raw_content

        source = payload.get("source", "unknown")
        ok = bool(payload.get("ok", False))
        data = str(payload.get("data", "")).strip()
        error = str(payload.get("error", "")).strip()

        if ok:
            return f"[{source}] {data or '（无返回内容）'}"
        return f"[{source}][ERROR] {error or '未知错误'}"
    except Exception:
        return raw_content


def collect_evidence(messages: list) -> list[dict]:
    """从工具消息中提取结构化证据，生成 E1/E2... 编号。"""
    evidence = []
    idx = 1
    for msg in messages:
        if getattr(msg, "type", "") != "tool":
            continue

        raw_content = getattr(msg, "content", "")
        try:
            payload = json.loads(raw_content)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        source = str(payload.get("source", "unknown")).strip()
        query = str(payload.get("query", "")).strip()
        ok = bool(payload.get("ok", False))
        data = str(payload.get("data", "")).strip()
        error = str(payload.get("error", "")).strip()

        # 只纳入有效工具返回；失败项可作为诊断信息但不计证据覆盖率
        if not ok or not data:
            continue

        snippet = data[:MAX_EVIDENCE_SNIPPET]
        evidence.append(
            {
                "id": f"E{idx}",
                "source": source,
                "query": query,
                "snippet": snippet,
                "full_text": data,
                "ok": ok,
                "error": error,
            }
        )
        idx += 1
    return evidence


def collect_vision_evidence(state: AgentState) -> list[dict]:
    """从 state 中提取视觉结构化证据，生成 V1/V2... 编号。"""
    mode = str(state.get("vision_mode", "general")).strip()
    image_name = str(state.get("vision_image_name", "")).strip()
    raw_summary = str(state.get("vision_context", "")).strip()
    ocr_text = str(state.get("vision_ocr_text", "")).strip()
    key_points = state.get("vision_key_points", []) or []
    chart_insights = state.get("vision_chart_insights", []) or []
    uncertainties = state.get("vision_uncertainties", []) or []

    entries: list[str] = []
    if raw_summary:
        entries.append(f"summary: {raw_summary}")
    if ocr_text:
        entries.append(f"ocr_text: {ocr_text}")
    if key_points:
        entries.append("key_points: " + "；".join(str(x) for x in key_points))
    if chart_insights:
        entries.append("chart_insights: " + "；".join(str(x) for x in chart_insights))
    if uncertainties:
        entries.append("uncertainties: " + "；".join(str(x) for x in uncertainties))

    if not entries:
        return []

    visual_text = "\n".join(entries)
    return [
        {
            "id": "V1",
            "source": "vision",
            "query": f"mode={mode}; image={image_name or 'unknown'}",
            "snippet": visual_text[:MAX_EVIDENCE_SNIPPET],
            "full_text": visual_text,
            "ok": True,
            "error": "",
        }
    ]


def collect_action_evidence(state: AgentState) -> list[dict]:
    """从 state 中提取动作执行结果，生成 A1/A2... 编号。"""
    results = state.get("action_results", []) or []
    evidence: list[dict] = []
    idx = 1
    for item in results:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).strip() or "unknown_action"
        status = str(item.get("status", "")).strip() or "unknown"
        message = str(item.get("message", "")).strip()
        output_path = str(item.get("output_path", "")).strip()
        command_output = str(item.get("command_output", "")).strip()
        summary = f"action={action}; status={status}; message={message}"
        if output_path:
            summary += f"; output_path={output_path}"
        if command_output:
            summary += f"; command_output={command_output[:300]}"

        evidence.append(
            {
                "id": f"A{idx}",
                "source": "action",
                "query": action,
                "snippet": summary[:MAX_EVIDENCE_SNIPPET],
                "full_text": summary,
                "ok": status == "executed",
                "error": "" if status == "executed" else message,
            }
        )
        idx += 1
    return evidence


def format_evidence_for_prompt(evidence_items: list[dict]) -> str:
    """将结构化证据格式化为提示词片段。"""
    if not evidence_items:
        return "无可用外部证据。"

    lines = []
    for item in evidence_items:
        lines.append(
            f"[{item['id']}] source={item['source']} | query={item['query']}\n"
            f"snippet={item['snippet']}"
        )
    return "\n\n".join(lines)


def extract_cited_evidence_ids(answer_text: str) -> set[str]:
    """提取回答中引用的证据编号，例如 [E1][V1][A1]。"""
    cited_ids = set()
    text = answer_text or ""
    i = 0
    while i < len(text):
        if text[i] == "[":
            j = text.find("]", i + 1)
            if j != -1:
                token = text[i + 1 : j].strip()
                if (token.startswith("E") or token.startswith("V") or token.startswith("A")) and token[1:].isdigit():
                    cited_ids.add(token)
                i = j + 1
                continue
        i += 1
    return cited_ids


def build_tool_context(messages: list) -> str:
    """提取工具上下文，用于 Critic/Synthesizer。"""
    context_str = ""
    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            tool_text = parse_tool_message(msg.content)
            context_str += f"\n[工具检索资料]: {tool_text}"
    return context_str.strip()


def build_dialog_context(messages: list) -> str:
    """提取用户、助手、工具的对话上下文。"""
    context_str = ""
    for msg in messages:
        msg_type = getattr(msg, "type", "")
        if msg_type == "human" and "【Critic 审查未通过】" not in msg.content:
            context_str += f"\n[用户]: {msg.content}"
        elif msg_type == "ai" and msg.content:
            context_str += f"\n[AI助手]: {msg.content}"
        elif msg_type == "tool":
            tool_text = parse_tool_message(msg.content)
            context_str += f"\n[工具检索资料]: {tool_text}"
    return context_str.strip()
