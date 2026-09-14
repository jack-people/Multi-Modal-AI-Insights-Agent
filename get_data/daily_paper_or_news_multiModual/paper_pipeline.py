import argparse
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    def tqdm(iterable, **kwargs):  # type: ignore
        return iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PDF_DIR = PROJECT_ROOT / "databank" / "paper_data" / "01_raw_pdfs"
CLEAN_MD_DIR = PROJECT_ROOT / "databank" / "paper_data" / "02_cleaned_mds"
TEMP_MINERU_DIR = PROJECT_ROOT / "databank" / "paper_data" / "03_temp_mineru"
TRACKER_FILE = PROJECT_ROOT / "databank" / "paper_data" / "arxiv_tracker.json"

FETCH_BATCH_SIZE = 50
SEARCH_QUERY = 'all:multimodal OR all:"vision-language model" OR all:"VLM"'

RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_MD_DIR.mkdir(parents=True, exist_ok=True)


def load_tracker() -> dict:
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"downloaded_ids": [], "last_start_index": 0}
    return {"downloaded_ids": [], "last_start_index": 0}


def save_tracker(tracker_data: dict) -> None:
    TRACKER_FILE.write_text(
        json.dumps(tracker_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|\n\r]', "", name).strip()


def step1_fetch_arxiv() -> None:
    try:
        import requests
    except Exception as e:
        print(f"[ERROR] 缺少 requests 依赖: {e}")
        print("请先安装: pip install requests")
        return

    print("\n" + "=" * 50)
    print("开始第一步：从 arXiv 抓取最新多模态论文")
    print("=" * 50)

    tracker = load_tracker()
    downloaded_ids = set(tracker.get("downloaded_ids", []))
    start_index = tracker.get("last_start_index", 0)
    collected_papers: list[dict] = []

    print("正在查询 arXiv API...")
    while len(collected_papers) < FETCH_BATCH_SIZE:
        query = urllib.parse.quote(SEARCH_QUERY)
        url = (
            "http://export.arxiv.org/api/query?"
            f"search_query={query}&start={start_index}"
            "&max_results=100&sortBy=submittedDate&sortOrder=descending"
        )

        try:
            response = urllib.request.urlopen(url, timeout=20)
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            if not entries:
                print("没有更多新论文。")
                break

            for entry in entries:
                if len(collected_papers) >= FETCH_BATCH_SIZE:
                    break

                paper_id_url = entry.find("atom:id", ns).text or ""
                paper_id = paper_id_url.split("/abs/")[-1].split("v")[0]
                title = sanitize_filename((entry.find("atom:title", ns).text or "").replace("\n", " "))

                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.attrib.get("title") == "pdf":
                        pdf_url = link.attrib.get("href", "")
                        break

                if paper_id and paper_id not in downloaded_ids and pdf_url:
                    collected_papers.append(
                        {"id": paper_id, "title": title, "pdf_url": pdf_url}
                    )

            start_index += 100
        except Exception as e:
            print(f"[ERROR] 请求 arXiv API 失败: {e}")
            break

    print(f"\n找到 {len(collected_papers)} 篇新论文，开始下载...")
    successful_downloads: list[str] = []

    for paper in tqdm(collected_papers, desc="下载 PDF"):
        file_path = RAW_PDF_DIR / f"[{paper['id']}] {paper['title']}.pdf"
        success = False
        for attempt in range(3):
            try:
                with requests.get(paper["pdf_url"], stream=True, timeout=15) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                success = True
                break
            except Exception as e:
                print(f"\n[WARN] 下载中断 {paper['id']} (尝试 {attempt + 1}/3): {e}")
                time.sleep(2)

        if success:
            successful_downloads.append(paper["id"])
            time.sleep(3)
        else:
            print(f"\n[ERROR] 下载失败并跳过: {paper['id']}")
            if file_path.exists():
                file_path.unlink()

    downloaded_ids.update(successful_downloads)
    tracker["downloaded_ids"] = list(downloaded_ids)
    tracker["last_start_index"] = start_index
    save_tracker(tracker)

    print(f"\n第一步完成，本次成功下载 {len(successful_downloads)} 篇。")
    print(f"输出目录: {RAW_PDF_DIR}")


def clean_markdown(input_md_path: Path, output_md_path: Path) -> tuple[bool, str]:
    try:
        content = input_md_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"\n#+\s*(References|Bibliography|Reference|参考文献)\b.*",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(content)
        cleaned_content = content[:match.start()] if match else content
        cleaned_content = re.sub(r"\n{4,}", "\n\n", cleaned_content)
        output_md_path.write_text(cleaned_content, encoding="utf-8")
        return True, "ok"
    except Exception as e:
        return False, str(e)


def step2_process_pdfs_local() -> None:
    print("\n" + "=" * 50)
    print("开始第二步：本地 MinerU 解析并清洗")
    print("=" * 50)

    pdf_files = list(RAW_PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[WARN] 未找到 PDF: {RAW_PDF_DIR}")
        return

    TEMP_MINERU_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_path in tqdm(pdf_files, desc="MinerU 解析中"):
        pdf_name = pdf_path.stem
        final_md_file = CLEAN_MD_DIR / f"{pdf_name}_clean.md"
        if final_md_file.exists():
            continue

        try:
            subprocess.run(
                ["magic-pdf", "pdf", "-p", str(pdf_path), "-o", str(TEMP_MINERU_DIR), "-m", "auto"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] MinerU 失败 {pdf_name}: {e.stderr}")
            continue

        miner_output_folder = TEMP_MINERU_DIR / pdf_name
        md_files = list(miner_output_folder.glob("*.md"))
        if not md_files:
            print(f"\n[WARN] 未生成 Markdown: {pdf_name}")
            continue

        ok, msg = clean_markdown(md_files[0], final_md_file)
        if not ok:
            print(f"\n[ERROR] 清洗失败 {pdf_name}: {msg}")

    shutil.rmtree(TEMP_MINERU_DIR, ignore_errors=True)
    print(f"\n第二步完成，输出目录: {CLEAN_MD_DIR}")


def step2_process_pdfs_online() -> None:
    print("\n[INFO] online 模式当前为占位流程。")
    print(f"请将在线 MinerU 结果放入: {CLEAN_MD_DIR}")


def step2_process_pdfs(mode: str = "local") -> None:
    if (mode or "local").strip().lower() == "online":
        step2_process_pdfs_online()
        return
    step2_process_pdfs_local()


def interactive_main() -> None:
    while True:
        print("\n" + "*" * 40)
        print("多模态论文处理工作流")
        print("*" * 40)
        print("1. 抓取最新论文（01_raw_pdfs）")
        print("2. 解析并清洗（02_cleaned_mds）")
        print("3. 退出")
        print("*" * 40)
        choice = input("请输入 (1/2/3): ").strip()
        if choice == "1":
            step1_fetch_arxiv()
        elif choice == "2":
            step2_process_pdfs()
        elif choice == "3":
            break
        else:
            print("[WARN] 输入无效。")


def main() -> None:
    parser = argparse.ArgumentParser(description="多模态论文采集与清洗流程")
    parser.add_argument(
        "--step",
        choices=["fetch", "process", "all", "interactive"],
        default="interactive",
        help="fetch=抓取，process=解析，all=两步，interactive=菜单",
    )
    parser.add_argument(
        "--process-mode",
        choices=["local", "online"],
        default="local",
        help="解析模式：local / online",
    )
    args = parser.parse_args()

    if args.step == "interactive":
        interactive_main()
        return
    if args.step == "fetch":
        step1_fetch_arxiv()
        return
    if args.step == "process":
        step2_process_pdfs(mode=args.process_mode)
        return

    step1_fetch_arxiv()
    step2_process_pdfs(mode=args.process_mode)


if __name__ == "__main__":
    main()
