# Retrieval benchmark

Run `tractor --benchmark`. It performs no network requests and exits nonzero when versioned regression thresholds fail. The dataset is packaged in the wheel and native bundle as `tractor/benchmark/fixtures-v1.json`.

Version 1.0.0 contains 16 original synthetic cases covering colliding personal/company names, corporate suffixes, Cyrillic/Arabic/Han/Japanese text, French/Spanish/German names, academic metadata, code projects, historical-name candidates, duplicate discovery, undated records, handles and domains. Each case specifies candidate judgments, source aliases, result-level relevance grades and duplicate groups. Unlisted distractors have grade zero. Labels describe fixture relevance, not the truth of a real-world claim. This is an engineering regression suite, not a representative web-search quality study.

Measurements include Recall@10/@50 within the finite labeled candidate set, MRR, nDCG@10, top-10 host/provider diversity, source types, languages, duplicate ratio, candidate precision, deduplication pair precision/recall, and local processing time. No network latency or requests-per-useful-result is fabricated: those fields are null for offline fixtures. The small candidate pools make Recall@50 an especially weak metric here. The benchmark intentionally retains difficult same-name negatives, so MRR and nDCG are below perfect.

Initial baseline with ranking version 2: Recall@10/@50 1.0, MRR 0.7188, nDCG@10 0.7960, candidate precision 0.8444, duplicate pair precision/recall 1.0. Runtime varies by machine. Candidate precision measures whether generated search hypotheses are acceptable fixture queries; it does not measure verified identity. The current duplicate fixture judgments emphasize exact URL copies; existing unit tests additionally exercise content hashes, near-text matching and conflicting identifiers. Expanding human-reviewed real-world judgments and near-copy benchmark sets remains necessary before claiming broad retrieval quality.

The production lexical/BM25 weights remain unchanged. Native provider ranks are preserved for inspection; rank fusion and semantic reranking are deferred until comparative benchmarks demonstrate a benefit. Do not adjust judgments simply to hide a regression. Change the fixture version when labels or case content change, and include rationale in the changelog.

## Live checks

Normal CI blocks real HTTP and skips integration tests. Explicit invocation may consume API credits:

```bash
TRACTOR_LIVE_TESTS=1 pytest -m integration -q
```

Only configured paid providers are tested. Mojeek additionally requires `TRACTOR_MOJEEK_STORAGE_ALLOWED=1`. The suite checks response normalization and one continuation when present; outages and rate limits fail the opt-in run honestly. A smaller diagnostic is `tractor --test-provider common_crawl` or another provider ID. Test requests use `climate` (or `example.org` for the Common Crawl index) and retain no investigation.

These checks validate contracts, not real-world recall. Use ordinary CLI searches and exported attempt/request metrics to collect a separately judged live evaluation corpus. Never include provider keys or private investigation data in committed fixtures.
