import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .schemas import SourceItem


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PDF_DIR = PROJECT_ROOT / "databank" / "paper_data" / "01_raw_pdfs"
PAPER_MD_DIR = PROJECT_ROOT / "databank" / "paper_data" / "02_cleaned_mds"
PAPER_DATA_DIR = PROJECT_ROOT / "databank" / "paper_data"
PAPER_FETCH_TRACKER = PAPER_DATA_DIR / "arxiv_tracker.json"
LATEST_ARXIV_BATCH_FILE = PAPER_DATA_DIR / "latest_arxiv_batch.json"
ARXIV_BATCH_HISTORY_DIR = PAPER_DATA_DIR / "batches"
NEWS_JSON_DIR = PROJECT_ROOT / "databank" / "news_data"

DEFAULT_PAPER_FETCH_QUERY = 'all:multimodal OR all:"vision-language model" OR all:"VLM"'


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _strip_markdown_noise(text: str) -> str:
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_title_from_md(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _load_tracker() -> dict:
    if PAPER_FETCH_TRACKER.exists():
        try:
            data = json.loads(PAPER_FETCH_TRACKER.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"downloaded_ids": [], "last_start_index": 0, "fetched_ids": []}


def _save_tracker(data: dict) -> None:
    PAPER_FETCH_TRACKER.parent.mkdir(parents=True, exist_ok=True)
    PAPER_FETCH_TRACKER.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _parse_arxiv_entries(xml_data: bytes) -> list[dict]:
    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    rows: list[dict] = []
    for entry in root.findall("atom:entry", ns):
        paper_id_url = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        paper_id = paper_id_url.split("/abs/")[-1].split("v")[0]
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").replace("\n", " ").strip()
        title = re.sub(r"\s+", " ", title)
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").replace("\n", " ").strip()
        summary = re.sub(r"\s+", " ", summary)
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
                break
        if paper_id and title:
            rows.append(
                {
                    "id": paper_id,
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "pdf_url": pdf_url,
                }
            )
    return rows


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|\n\r]', "", name).strip()


def _download_pdf_if_needed(
    paper: dict,
    downloaded_ids: set[str],
    timeout_sec: int,
    max_retries: int,
) -> tuple[bool, str]:
    paper_id = str(paper.get("id", "")).strip()
    title = _sanitize_filename(str(paper.get("title", "")).strip())
    pdf_url = str(paper.get("pdf_url", "")).strip()
    if not paper_id or not title or not pdf_url:
        return False, f"论文信息不完整，跳过下载: id={paper_id}"
    if paper_id in downloaded_ids:
        return False, f"已在下载记录中，跳过: {paper_id}"

    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RAW_PDF_DIR / f"[{paper_id}] {title}.pdf"
    if output_path.exists():
        downloaded_ids.add(paper_id)
        return False, f"本地已存在，跳过: {output_path.name}"

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(pdf_url, timeout=timeout_sec) as resp, open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
            downloaded_ids.add(paper_id)
            return True, f"下载成功: {output_path.name}"
        except Exception as e:
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            if attempt >= max_retries:
                return False, f"下载失败({paper_id})，重试耗尽: {e}"
    return False, f"下载失败({paper_id})"


def fetch_latest_arxiv_batch(
    limit: int = 10,
    query: str = DEFAULT_PAPER_FETCH_QUERY,
) -> tuple[list[dict], list[str]]:
    """
    每次运行抓取“最新且未抓过”的论文元数据，不下载 PDF，避免流程过慢。
    去重依据：arxiv_tracker.json 中 fetched_ids。
    """
    warnings: list[str] = []
    tracker = _load_tracker()
    fetched_ids = set(tracker.get("fetched_ids", []))
    collected: list[dict] = []

    page = 0
    page_size = 50
    max_pages = 6  # 最多扫描 300 条，避免无限请求
    encoded_query = urllib.parse.quote(query)
    while len(collected) < limit and page < max_pages:
        start = page * page_size
        url = (
            "http://export.arxiv.org/api/query?"
            f"search_query={encoded_query}&start={start}"
            f"&max_results={page_size}&sortBy=submittedDate&sortOrder=descending"
        )
        try:
            response = urllib.request.urlopen(url, timeout=20)
            rows = _parse_arxiv_entries(response.read())
        except Exception as e:
            warnings.append(f"拉取 arXiv 失败(page={page}): {e}")
            break

        if not rows:
            break
        for row in rows:
            if len(collected) >= limit:
                break
            if row["id"] in fetched_ids:
                continue
            collected.append(row)
            fetched_ids.add(row["id"])
        page += 1

    if collected:
        batch_payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "limit": limit,
            "papers": collected,
        }
        PAPER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        LATEST_ARXIV_BATCH_FILE.write_text(
            json.dumps(batch_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 保留历史批次（避免只覆盖 latest_arxiv_batch.json 看不到新增）
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ARXIV_BATCH_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        history_file = ARXIV_BATCH_HISTORY_DIR / f"arxiv_batch_{ts}.json"
        # 同秒重复运行兜底
        i = 1
        while history_file.exists():
            history_file = ARXIV_BATCH_HISTORY_DIR / f"arxiv_batch_{ts}_{i}.json"
            i += 1
        history_file.write_text(
            json.dumps(batch_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 可选：自动下载 PDF 到 01_raw_pdfs
        should_download_pdf = _env_bool("PAPER_DOWNLOAD_PDF_ON_RUN", True)
        downloaded_ids = set(tracker.get("downloaded_ids", []))
        if should_download_pdf:
            download_timeout = _env_int("PAPER_PDF_DOWNLOAD_TIMEOUT_SEC", 30)
            download_retries = max(1, _env_int("PAPER_PDF_DOWNLOAD_RETRIES", 2))
            success_count = 0
            for row in collected:
                ok, msg = _download_pdf_if_needed(
                    paper=row,
                    downloaded_ids=downloaded_ids,
                    timeout_sec=download_timeout,
                    max_retries=download_retries,
                )
                warnings.append(msg)
                if ok:
                    success_count += 1
            warnings.append(f"PDF 下载完成: 成功 {success_count}/{len(collected)}")
            tracker["downloaded_ids"] = list(downloaded_ids)[-10000:]
        tracker["fetched_ids"] = list(fetched_ids)[-10000:]
        _save_tracker(tracker)
        warnings.append(f"论文批次已保存: {history_file}")
    else:
        warnings.append("本次未获取到新的 arXiv 论文（可能已全部抓取过）。")
    return collected, warnings


def _load_latest_batch_as_sources(limit: int = 10) -> tuple[list[SourceItem], list[str]]:
    warnings: list[str] = []
    if not LATEST_ARXIV_BATCH_FILE.exists():
        return [], [f"最新论文批次文件不存在: {LATEST_ARXIV_BATCH_FILE}"]
    try:
        payload = json.loads(LATEST_ARXIV_BATCH_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return [], [f"读取最新论文批次文件失败: {e}"]
    papers = payload.get("papers", [])
    if not isinstance(papers, list):
        return [], ["latest_arxiv_batch.json 结构异常。"]
    items: list[SourceItem] = []
    for row in papers[:limit]:
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        paper_id = str(row.get("id", "")).strip()
        summary = str(row.get("summary", "")).strip()
        published = str(row.get("published", "")).strip()
        pdf_url = str(row.get("pdf_url", "")).strip()
        content = (
            f"title: {title}\n"
            f"id: {paper_id}\n"
            f"published: {published}\n"
            f"summary: {summary}\n"
            f"pdf_url: {pdf_url}"
        )
        items.append(
            SourceItem(
                source_type="paper",
                title=title,
                content=content[:8000],
                source_path=str(LATEST_ARXIV_BATCH_FILE),
                published_at=published,
            )
        )
    if not items:
        warnings.append("最新论文批次中没有可用条目。")
    return items, warnings


def load_latest_papers_with_meta(limit: int = 30) -> tuple[list[SourceItem], list[str]]:
    warnings: list[str] = []
    # 优先使用“每次运行自动抓取”的最新论文批次
    only_latest_batch = _env_bool("PAPER_ONLY_USE_LATEST_BATCH", True)
    if only_latest_batch:
        items, batch_warn = _load_latest_batch_as_sources(limit=limit)
        warnings.extend(batch_warn)
        return items, warnings

    # 兼容旧流程：从清洗后的 markdown 读取
    if not PAPER_MD_DIR.exists():
        return [], [f"论文目录不存在: {PAPER_MD_DIR}"]
    files = sorted(PAPER_MD_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    items: list[SourceItem] = []
    for file in files:
        try:
            raw = file.read_text(encoding="utf-8", errors="ignore")
            content = _strip_markdown_noise(raw)
            title = _extract_title_from_md(content, file.stem)
            items.append(
                SourceItem(
                    source_type="paper",
                    title=title,
                    content=content[:8000],
                    source_path=str(file),
                )
            )
        except Exception as e:
            warnings.append(f"读取论文失败: {file.name} ({e})")
            continue
    return items, warnings


def load_latest_news(limit: int = 30) -> list[SourceItem]:
    if not NEWS_JSON_DIR.exists():
        return []
    news_files = sorted(
        NEWS_JSON_DIR.glob("multimodal_news_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    items: list[SourceItem] = []
    for file in news_files:
        if len(items) >= limit:
            break
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in payload.get("new_items", []):
            if len(items) >= limit:
                break
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            content = f"{title}\n来源: {row.get('source', '')}\n链接: {row.get('link', '')}"
            items.append(
                SourceItem(
                    source_type="news",
                    title=title,
                    content=content,
                    source_path=str(file),
                    published_at=str(row.get("pub_date", "")),
                )
            )
    return items


def load_latest_news_with_meta(limit: int = 30) -> tuple[list[SourceItem], list[str]]:
    warnings: list[str] = []
    if not NEWS_JSON_DIR.exists():
        return [], [f"新闻目录不存在: {NEWS_JSON_DIR}"]
    news_files = sorted(
        NEWS_JSON_DIR.glob("multimodal_news_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not news_files:
        warnings.append("新闻目录存在但暂无采集结果（multimodal_news_*.json）。")
    items: list[SourceItem] = []
    for file in news_files:
        if len(items) >= limit:
            break
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except Exception as e:
            warnings.append(f"读取新闻文件失败: {file.name} ({e})")
            continue
        rows = payload.get("new_items", [])
        if not isinstance(rows, list):
            warnings.append(f"新闻文件结构异常: {file.name}")
            continue
        for row in rows:
            if len(items) >= limit:
                break
            title = str(row.get("title", "")).strip()
            if not title:
                continue
            content = f"{title}\n来源: {row.get('source', '')}\n链接: {row.get('link', '')}"
            items.append(
                SourceItem(
                    source_type="news",
                    title=title,
                    content=content,
                    source_path=str(file),
                    published_at=str(row.get("pub_date", "")),
                )
            )
    return items, warnings


def load_multimodal_sources(paper_limit: int = 30, news_limit: int = 30) -> list[SourceItem]:
    items, _warnings = load_multimodal_sources_with_meta(paper_limit=paper_limit, news_limit=news_limit)
    return items


def load_multimodal_sources_with_meta(
    paper_limit: int = 30,
    news_limit: int = 30,
) -> tuple[list[SourceItem], list[str]]:
    warnings: list[str] = []
    auto_fetch = _env_bool("PAPER_AUTO_FETCH_ON_RUN", True)
    fetch_limit = _env_int("PAPER_FETCH_LIMIT_PER_RUN", 10)
    fetch_query = os.getenv("PAPER_FETCH_QUERY", DEFAULT_PAPER_FETCH_QUERY)
    fetch_loop_count = max(1, _env_int("PAPER_FETCH_LOOP_COUNT", 10))
    fetch_interval_minutes = max(0, _env_int("PAPER_FETCH_INTERVAL_MINUTES", 30))
    if auto_fetch:
        total_new = 0
        for idx in range(fetch_loop_count):
            round_no = idx + 1
            fetched, fetch_warn = fetch_latest_arxiv_batch(limit=max(1, fetch_limit), query=fetch_query)
            total_new += len(fetched)
            warnings.extend([f"[第{round_no}轮] {w}" for w in fetch_warn])
            if fetched:
                warnings.append(f"[第{round_no}轮] 新抓取论文 {len(fetched)} 篇（去重后）。")
            if round_no < fetch_loop_count and fetch_interval_minutes > 0:
                warnings.append(f"[第{round_no}轮] 等待 {fetch_interval_minutes} 分钟后进入下一轮。")
                time.sleep(fetch_interval_minutes * 60)
        warnings.append(f"抓取循环完成：共 {fetch_loop_count} 轮，累计新增 {total_new} 篇。")

    papers, p_warn = load_latest_papers_with_meta(limit=paper_limit)
    warnings.extend(p_warn)
    if news_limit > 0:
        news, n_warn = load_latest_news_with_meta(limit=news_limit)
        warnings.extend(n_warn)
        return papers + news, warnings
    return papers, warnings
