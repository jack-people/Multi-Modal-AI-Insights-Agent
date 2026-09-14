from collections import Counter

from .schemas import SourceItem


KEYWORDS = {
    "agent": ["agent", "multi-agent", "agentic"],
    "vlm": ["vlm", "vision-language", "mllm", "multimodal"],
    "reasoning": ["reasoning", "planning", "grounded", "world model"],
    "efficiency": ["pruning", "quantization", "efficient", "lightweight"],
    "safety": ["safety", "jailbreak", "attack", "guard"],
}


def score_source(item: SourceItem) -> float:
    text = f"{item.title}\n{item.content}".lower()
    score = 1.0
    for words in KEYWORDS.values():
        if any(w in text for w in words):
            score += 1.0
    if item.source_type == "paper":
        score += 0.5
    return score


def tag_source(item: SourceItem) -> list[str]:
    text = f"{item.title}\n{item.content}".lower()
    tags: list[str] = []
    for tag, words in KEYWORDS.items():
        if any(w in text for w in words):
            tags.append(tag)
    return tags or ["general"]


def prepare_sources(items: list[SourceItem], keep_top_k: int = 20) -> list[SourceItem]:
    prepared: list[SourceItem] = []
    for it in items:
        it.score = score_source(it)
        it.tags = tag_source(it)
        prepared.append(it)
    prepared.sort(key=lambda x: x.score, reverse=True)
    return prepared[:keep_top_k]


def build_stats(items: list[SourceItem]) -> dict:
    counter = Counter()
    for it in items:
        counter.update(it.tags)
    return dict(counter)
