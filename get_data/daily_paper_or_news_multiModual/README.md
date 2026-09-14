# 日更多模态数据入口

目录：`get_data/daily_paper_or_news_multiModual`

这个目录是“多模态信息获取”的统一入口，包含两类采集：

- 论文：`paper_pipeline.py`（arXiv + PDF 清洗）
- 新闻：新增 Google News RSS 的多模态相关资讯抓取

## 常用命令

仅抓论文（只跑第一步下载）：

```bash
python get_data/daily_paper_or_news_multiModual/daily_fetch.py --target papers --paper-step fetch
```

仅抓新闻：

```bash
python get_data/daily_paper_or_news_multiModual/daily_fetch.py --target news --news-limit 20
```

论文 + 新闻一起抓：

```bash
python get_data/daily_paper_or_news_multiModual/daily_fetch.py --target all --paper-step fetch --news-limit 20
```

## 输出位置

- 论文输出：沿用 `databank/paper_data/...`
- 新闻输出：`databank/news_data/multimodal_news_*.json`
- 新闻去重记录：`databank/news_data/news_tracker.json`

## 说明

- 建议统一从这个目录调度，便于你做“每天 8 点”定时任务。
