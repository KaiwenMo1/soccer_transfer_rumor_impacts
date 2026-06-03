# Scrapling Benchmark

Generated: 2026-06-02

## Setup

Small benchmark over:

- clubs: Manchester United, Juventus, Ajax NV
- window: 2026-05-26 to 2026-06-02
- max records: 5
- discovery source preset: `fast_no_api`

## Result

| Run | Articles | Decoded URLs | Bodies >= 400 chars | Avg body chars | Unique sources | Live watchlist rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RSS only | 13 | 0 | 0 | 0.0 | 1 | 3 |
| RSS + Scrapling, no decode | 13 | 0 | 0 | 0.0 | 1 | not analyzed |
| RSS + Google decode + Scrapling | 13 | 13 | 13 | 4001.4 | 13 | 4 |

## Takeaway

Scrapling alone does not help much with Google News RSS results because those
URLs are wrapper pages. The useful pattern is:

1. discover articles with RSS
2. decode Google News wrapper URLs into publisher URLs
3. enrich article bodies with Scrapling
4. run the normal claim/match/credibility pipeline

## Commands

```bash
.venv/bin/python -m transfer_stock.cli refresh-live-fetch \
  --start 2026-05-26 \
  --end 2026-06-02 \
  --source-preset fast_no_api \
  --methods rss google-news-decode scrapling \
  --max-records 5 \
  --pause 0 \
  --clubs manchester_united juventus ajax \
  --output data/raw/articles/benchmark_decode_scrapling.jsonl
```

```bash
.venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/benchmark_decode_scrapling.jsonl \
  --clubs manchester_united juventus ajax \
  --slug benchmark_decode_scrapling \
  --dashboard-output app/static/data/dashboard_data_scrapling_benchmark.json
```

## Dependency Note

Current Scrapling releases require `lxml >= 6`, while installed Fundus/Crawl4AI
versions currently expect `lxml < 6` or `lxml ~= 5.3`. Treat Scrapling mode as a
separate enrichment lane from Fundus/Crawl4AI until those dependency ranges
align.

