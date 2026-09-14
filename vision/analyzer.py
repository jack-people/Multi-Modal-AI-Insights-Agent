import base64
import json
from typing import Any, Literal
import requests
from model import VISION_MODEL
from config import (
    VISION_ENABLED,
    VISION_TIMEOUT_SEC,
    VISION_API_URL,
    VISION_API_KEY,
)
from runtime_context import log_event

VisionMode = Literal["general", "ocr", "chart"]


def _build_vision_prompt(mode: VisionMode, user_prompt: str) -> str:
    custom = user_prompt.strip()
    if custom:
        return custom

    mode_instructions = {
        "general": "聚焦对象、场景、可读文字与可用于问答的关键点。",
        "ocr": "聚焦文字提取与关键数值，尽量逐字保真。",
        "chart": "聚焦图表类型、坐标轴、趋势对比、极值与结论。",
    }
    return (
        "请严格输出 JSON（不要 Markdown，不要代码块），字段如下："
        '{"raw_summary":"","ocr_text":"","key_points":[],"chart_insights":[],"uncertainties":[]}'
        f"\n当前模式：{mode}。模式说明：{mode_instructions[mode]}"
        f"\n用户补充要求：{custom or '无'}"
    )


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _extract_first_json_object(text: str) -> dict:
    raw = text.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def analyze_image_bytes(
    image_bytes: bytes,
    mime_type: str = "image/png",
    prompt: str = "",
    mode: VisionMode = "general",
) -> dict:
    """调用视觉模型，返回图片分析文本与结构化字段。"""
    if not VISION_ENABLED:
        return {"ok": False, "text": "", "error": "视觉能力未开启（VISION_ENABLED=false）"}
    if not image_bytes:
        return {"ok": False, "text": "", "error": "图片内容为空"}

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{image_b64}"
    user_text = _build_vision_prompt(mode, prompt)

    headers = {
        "Authorization": f"Bearer {VISION_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.1,
    }

    try:
        log_event(
            "vision_analyzer",
            "start",
            meta={"bytes": len(image_bytes), "model": VISION_MODEL, "mode": mode},
        )
        response = requests.post(
            VISION_API_URL,
            headers=headers,
            json=payload,
            timeout=VISION_TIMEOUT_SEC,
        )
        if response.status_code != 200:
            error = f"Vision HTTP错误: {response.status_code} {response.text}"
            log_event("vision_analyzer", "error", meta={"error": error})
            return {"ok": False, "text": "", "error": error}

        result = response.json()
        raw_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = str(raw_content).strip()
        if not text:
            error = "视觉模型未返回可用文本"
            log_event("vision_analyzer", "error", meta={"error": error})
            return {"ok": False, "text": "", "error": error}

        parsed = _extract_first_json_object(text)
        raw_summary = str(parsed.get("raw_summary", "")).strip() or text
        ocr_text = str(parsed.get("ocr_text", "")).strip()
        key_points = _safe_list(parsed.get("key_points"))
        chart_insights = _safe_list(parsed.get("chart_insights"))
        uncertainties = _safe_list(parsed.get("uncertainties"))

        sections = [f"[VISION_MODE={mode}]", raw_summary]
        if ocr_text:
            sections.append(f"OCR文本: {ocr_text}")
        if key_points:
            sections.append("关键点: " + "；".join(key_points))
        if chart_insights:
            sections.append("图表洞察: " + "；".join(chart_insights))
        if uncertainties:
            sections.append("不确定项: " + "；".join(uncertainties))
        final_text = "\n".join(sections)

        log_event("vision_analyzer", "done", meta={"chars": len(final_text), "mode": mode})
        return {
            "ok": True,
            "text": final_text,
            "error": "",
            "mode": mode,
            "raw_summary": raw_summary,
            "ocr_text": ocr_text,
            "key_points": key_points,
            "chart_insights": chart_insights,
            "uncertainties": uncertainties,
        }
    except Exception as e:
        error = f"Vision 调用异常: {e}"
        log_event("vision_analyzer", "error", meta={"error": str(e)})
        return {"ok": False, "text": "", "error": error}
