def infer_profile_updates(user_text: str) -> dict:
    """
    从用户文本里提取可持久化的偏好更新。
    规则保持保守：仅在出现明确偏好表达时更新。
    """
    text = (user_text or "").strip().lower()
    if not text:
        return {}

    updates: dict = {}

    concise_hits = ["简短", "简洁", "精简", "短一点", "别太长", "精炼", "concise"]
    detailed_hits = ["详细", "展开", "讲细", "多写点", "细一点", "detailed"]
    structure_on_hits = ["分点", "条目", "结构化", "列表", "有层次", "按点", "use structure"]
    structure_off_hits = ["不要分点", "别分点", "不要列表", "别列表", "一段话"]
    casual_hits = ["轻松", "口语", "随意", "casual"]
    professional_hits = ["专业", "正式", "严谨", "professional"]

    if any(k in text for k in concise_hits):
        updates["answer_style"] = "concise"
    if any(k in text for k in detailed_hits):
        updates["answer_style"] = "detailed"
    if any(k in text for k in structure_on_hits):
        updates["use_structure"] = True
    if any(k in text for k in structure_off_hits):
        updates["use_structure"] = False
    if any(k in text for k in casual_hits):
        updates["tone"] = "casual"
    if any(k in text for k in professional_hits):
        updates["tone"] = "professional"

    return updates
