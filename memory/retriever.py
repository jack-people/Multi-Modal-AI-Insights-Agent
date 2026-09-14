import re


def _tokenize(text: str) -> set[str]:
    content = (text or "").lower()
    tokens = set(re.findall(r"[a-zA-Z0-9_]{2,}", content))

    zh_chunks = re.findall(r"[\u4e00-\u9fff]+", content)
    for chunk in zh_chunks:
        if len(chunk) >= 2:
            for i in range(len(chunk) - 1):
                tokens.add(chunk[i : i + 2])
        else:
            tokens.add(chunk)
    return tokens


def select_relevant_memory_notes(notes: list[str], query: str, top_k: int = 5) -> list[str]:
    """按关键词重合度选择与当前问题最相关的长期记忆。"""
    if not notes:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return notes[: max(1, int(top_k))]

    scored: list[tuple[int, int, str]] = []
    for idx, note in enumerate(notes):
        n_tokens = _tokenize(note)
        score = len(q_tokens.intersection(n_tokens))
        scored.append((score, idx, note))

    # 优先高相关，其次靠后写入（idx 大）
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    selected = [note for score, _, note in scored if score > 0][: max(1, int(top_k))]
    if selected:
        return selected
    # 无相关重合时回退最近写入的几条
    return notes[-max(1, int(top_k)) :]
