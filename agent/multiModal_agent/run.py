import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from .agent import MultiModalAnalysisAgent
from .log_utils import is_debug_enabled, setup_logger

logger = setup_logger("multiModal_agent.run")


def _build_timestamped_output_path(output_dir: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"multimodal_initial_report_{ts}.json"
    # 同秒内重复运行时避免冲突
    i = 1
    while path.exists():
        path = base / f"multimodal_initial_report_{ts}_{i}.json"
        i += 1
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="多模态子Agent：数据处理 -> 初步分析 -> 总结")
    default_paper_limit = int(os.getenv("PAPER_FETCH_LIMIT_PER_RUN", "10"))
    default_news_limit = int(os.getenv("MULTIMODAL_AGENT_NEWS_LIMIT", "0"))
    default_top_k = int(os.getenv("MULTIMODAL_AGENT_TOP_K", str(default_paper_limit)))
    parser.add_argument("--paper-limit", type=int, default=default_paper_limit, help="读取论文条数上限")
    parser.add_argument("--news-limit", type=int, default=default_news_limit, help="读取新闻条数上限")
    parser.add_argument("--top-k", type=int, default=default_top_k, help="送入模型分析的样本上限")
    parser.add_argument("--output", default="", help="输出报告完整路径（可选，不传则自动按时间命名）")
    parser.add_argument(
        "--output-dir",
        default="output/multiModal_agent",
        help="自动命名时的输出目录",
    )
    parser.add_argument(
        "--fail-on-fallback",
        action="store_true",
        help="当模型进入 fallback 时以非0退出，便于CI/调度系统告警",
    )
    args = parser.parse_args()

    logger.info("命令参数: paper_limit=%s news_limit=%s top_k=%s", args.paper_limit, args.news_limit, args.top_k)
    agent = MultiModalAnalysisAgent()
    report = agent.run(
        paper_limit=args.paper_limit,
        news_limit=args.news_limit,
        top_k=args.top_k,
    )

    out_path = Path(args.output) if args.output else _build_timestamped_output_path(args.output_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.__dict__, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] 子Agent分析完成，报告输出: {out_path}")
    if is_debug_enabled():
        print(f"[INFO] model_status={report.model_status}, model_attempts={report.model_attempts}")
        if report.processing_warnings:
            print("[WARN] processing_warnings:")
            for w in report.processing_warnings:
                print(f"  - {w}")
    if args.fail_on_fallback and report.model_status != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
