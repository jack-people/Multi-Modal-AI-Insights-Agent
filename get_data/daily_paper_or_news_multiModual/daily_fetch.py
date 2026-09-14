import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_SCRIPT = PROJECT_ROOT / "get_data" / "daily_paper_or_news_multiModual" / "paper_pipeline.py"

# 新闻落盘目录（可按需改到数据库）
NEWS_DIR = PROJECT_ROOT / "databank" / "news_data"
NEWS_TRACKER_FILE = NEWS_DIR / "news_tracker.json"

# 多模态关键词（用于 Google News RSS）
NEWS_QUERY = "multimodal AI OR vision language model OR agentic AI"
NEWS_LANG = "zh-CN"
NEWS_REGION = "CN"


def _ensure_news_dirs() -> None:
    NEWS_DIR.mkdir(parents=True, exist_ok=True)


def _load_news_tracker() -> dict:
    if NEWS_TRACKER_FILE.exists():
        try:
            return json.loads(NEWS_TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"seen_links": []}
    return {"seen_links": []}


def _save_news_tracker(data: dict) -> None:
    NEWS_TRACKER_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_news_rss(max_items: int = 20) -> list[dict]:
    query = urllib.parse.quote(NEWS_QUERY)
    url = (
        "https://news.google.com/rss/search?"
        f"q={query}&hl={NEWS_LANG}&gl={NEWS_REGION}&ceid={NEWS_REGION}:{NEWS_LANG}"
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        xml_data = resp.read()
    root = ET.fromstring(xml_data)

    items: list[dict] = []
    channel = root.find("channel")
    if channel is None:
        return items

    for item in channel.findall("item")[:max_items]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_node = item.find("source")
        source = (source_node.text or "").strip() if source_node is not None else ""
        if link:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "source": source,
                }
            )
    return items


def run_news_fetch(max_items: int = 20) -> Path:
    _ensure_news_dirs()
    tracker = _load_news_tracker()
    seen_links = set(tracker.get("seen_links", []))

    all_items = _fetch_news_rss(max_items=max_items)
    new_items = [it for it in all_items if it["link"] not in seen_links]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = NEWS_DIR / f"multimodal_news_{timestamp}.json"
    out_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "query": NEWS_QUERY,
        "total_fetched": len(all_items),
        "new_items": new_items,
    }
    out_file.write_text(
        json.dumps(out_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    seen_links.update([it["link"] for it in new_items])
    tracker["seen_links"] = list(seen_links)[-5000:]
    _save_news_tracker(tracker)
    return out_file


def run_paper_pipeline(paper_step: str, process_mode: str) -> int:
    if not PAPER_SCRIPT.exists():
        print(f"[ERROR] 未找到脚本: {PAPER_SCRIPT}")
        return 1
    cmd = [
        sys.executable,
        str(PAPER_SCRIPT),
        "--step",
        paper_step,
        "--process-mode",
        process_mode,
    ]
    print(f"▶ 运行论文流程: {' '.join(cmd)}")
    completed = subprocess.run(cmd)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="多模态数据每日采集统一入口（论文 + 新闻）")
    parser.add_argument(
        "--target",
        choices=["papers", "news", "all"],
        default="all",
        help="采集目标：papers / news / all",
    )
    parser.add_argument(
        "--paper-step",
        choices=["fetch", "process", "all"],
        default="fetch",
        help="论文流程步骤（会转发到 paper_pipeline.py）",
    )
    parser.add_argument(
        "--process-mode",
        choices=["local", "online"],
        default="local",
        help="论文第二步处理模式（local 或 online）",
    )
    parser.add_argument(
        "--news-limit",
        type=int,
        default=20,
        help="新闻最大抓取条数",
    )
    args = parser.parse_args()

    if args.target in {"papers", "all"}:
        rc = run_paper_pipeline(args.paper_step, args.process_mode)
        if rc != 0:
            return rc
        # 避免连续请求造成资源高峰
        time.sleep(1)

    if args.target in {"news", "all"}:
        try:
            out_file = run_news_fetch(max_items=args.news_limit)
            print(f"[OK] 新闻采集完成，输出: {out_file}")
        except Exception as e:
            print(f"[ERROR] 新闻采集失败: {e}")
            return 1

    print("[DONE] 多模态数据采集流程执行完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
