TRACTOR 0.4 — Coverage

This release broadens source discovery while keeping original evidence, explicit limits and resumable searches.

- Optional Brave, Mojeek and current Kagi v1 search APIs; Marginalia with shared-development/private credentials.
- Expanded SearxNG upstream metadata, visible partial failures and resumable pages.
- Common Crawl capture metadata for known URLs/domains, without destination or WARC downloads.
- Provider capabilities, grouped Settings, profiles, language/freshness controls, configurable bounded budgets and a privacy screen.
- Local provider health, independent-index discovery counts, retained duplicate discovery paths, expanded query candidates and 25-language Wikidata labels.
- CLI provider diagnostics, coverage reports, refresh and expanded exports; versioned offline benchmark.
- Authenticated caches stay in memory; keys are redacted from storage, logs and exports. Existing database history migrates automatically.

Download the native archive matching your system and architecture, extract it fully, and open Tractor. Native builds are unsigned; Tor remains an optional external dependency. Source archives and a Python wheel are also attached. SHA256SUMS.txt covers each artifact.

Known limits: paid APIs were contract-tested with fixtures when keys were unavailable. The public Marginalia key can be rate-limited. Search snippets are not full documents, index agreement is not factual confirmation, and no search is exhaustive. Claims, source-independence analysis, document/PDF retrieval, timelines, translation integration and large-scale persistence redesign remain later milestones. See docs/roadmap.md.
