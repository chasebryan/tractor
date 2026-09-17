# Adding a provider

Adapters are trusted application code. Register the adapter in `sources/catalog.py`, declare implemented `ProviderCapabilities`, and return `SearchBatch` from `search(QueryVariant, SearchContext)`. Use `context.client`; do not create an independent HTTP client or filesystem downloader in an adapter. Official API hosts belong in the network allowlist, while custom SearxNG servers register an exact validated origin.

Use the `Credentials` abstraction and fixed-origin `RequestAuth`. Do not accept keys in URLs from users or save keys in settings. Authentication must be applied inside the network layer, after destination validation. Authenticated redirects are disabled. Request keys include route, provider, query parameters/body, and an in-memory credential scope. Do not add telemetry or persist a private response cache.

Return bounded, normalized `SourceResult` records with original text, provider-native rank, date semantics, API record metadata where reasonable, and lineage/scope labels. Search snippets and archive index entries are not full destination documents. Preserve license metadata. Do not convert generated answers into source evidence.

A `next_cursor` must preserve every remaining record in a provider page, even when the user changes the per-query result budget on continuation. Record collection IDs and offsets where necessary. A changed server, account or search configuration must invalidate saved cursors explicitly. Do not infer pagination solely by discarding excess results.

A malformed, unauthorized, rate-limited or unavailable response raises `SourceUnavailable` with a safe category and message. Never include response bodies or request URLs in error text. Use `partial=True` and warnings when valid results coexist with upstream failures: the engine retains evidence and retries the same page. Use `skipped_reason` for inapplicable query forms, not an invented successful empty result.

Query candidates require a retained parent result and evidence URLs. Mechanical transformations remain hypotheses. Provider capabilities govern operator-specific variants. Shared names, hosting or discovery indexes do not establish identity, ownership, independence or truth.

Required tests: request contract/authentication, valid empty response, malformed response, pagination and changed budgets, rate limit, timeout/cancellation, redirects, bounded content, credential leakage, persistence/resume, and export metadata. Add a small explicitly opt-in live test where feasible. Ordinary CI must not depend on provider uptime or paid credentials.
