def extract_high_value_memory(text: str) -> str:
    """
    从用户输入中提取“高价值长期记忆”候选。
    返回空字符串表示不写入长期记忆。
    """
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw:
        return ""

    trigger_keywords = [
        "记住",
        "以后",
        "长期",
        "我的目标",
        "我在做",
        "我主要",
        "请一直",
        "约束",
        "偏好",
        "习惯",
        "always",
        "remember",
    ]
    if not any(k in lower for k in trigger_keywords):
        return ""

    # 避免把纯命令型短句写入长期记忆
    if len(raw) < 8:
        return ""
    return raw[:300]
