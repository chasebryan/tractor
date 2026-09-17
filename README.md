# TRACTOR

**Global Intelligence Search**

A native, local-first desktop application for evidence-led research across independent public data sources. Enter one subject. TRACTOR constructs a traceable query plan, retrieves records asynchronously, investigates discovered multilingual label candidates, groups duplicates, ranks results, and saves the investigation locally.

This repository implements the initial end-to-end MVP. It reports exactly which providers and queries were attempted. A finished investigation does not imply exhaustive coverage.

## Run

Use **Python 3.11–3.13** (3.12 recommended). Qt 6.8 is pinned for compatibility with older desktop CPUs. No API keys are required for the included providers.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
tractor
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. On Linux, Qt needs your distribution's desktop graphics libraries; minimal systems may need `libegl1`, `libopengl0`, and the Qt xcb dependencies. The app can also use Wayland. Windows and macOS are intended targets, but this first implementation has been exercised on Linux.

For an explicitly selected data location:

```bash
tractor --data-dir ./local-investigations
```

The same engine runs without Qt windows:

```bash
tractor --search "OpenStreetMap" --export-json investigation.json
```

The CLI uses all built-in providers. Desktop provider choices are saved in Settings.

## Search experience

- A restrained home screen with one large search field, History, and Settings.
- Results stream while background work continues. Stop cancels outstanding work and retains collected evidence.
- Each card includes source category, provider, date, language, relevance, source link, evidence, and related records.
- Evidence shows the original text, query chain, ranking components, content hash, and provider metadata. All previews are plain text. “Open source” explicitly opens your external browser.
- Coverage lists source attempts, errors, queries, request/cache counts, languages, pass yields, limits, candidate aliases, and the evidence graph.
- Post-collection filters cover text, category, provider, language, domain, date, observed region, entity type, and relevance. Unknown dates and geography remain unknown.
- History reopens saved results and evidence. Interrupted investigations are labeled as such.
- Export complete JSON, a cited Markdown report, or spreadsheet-safe CSV. JSON retains duplicate records, original provider payloads, query states, entities, edges, attempts, budgets, and timestamps.

## Included public sources

| Adapter | Coverage | API reference |
| --- | --- | --- |
| Wikidata | Knowledge records and multilingual label candidates; not an official company registry | [Wikibase API](https://www.mediawiki.org/wiki/Wikibase/API) |
| Crossref | Publication metadata, available abstracts, and DOI identifiers | [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) |
| Internet Archive | Archived item catalog metadata; not a Wayback-wide crawl | [Internet Archive developer portal](https://archive.org/developers/) |
| GitHub | Public repository names and descriptions; not authenticated code search | [GitHub search API](https://docs.github.com/en/rest/search/search#search-repositories) |

An API may be unavailable, rate-limited, or have limited coverage. TRACTOR records that outcome. These four providers do not constitute a general index of the web. Requests use explicit language settings independent of browser history, browser locale, or OS locale.

The default investigation budget is 3 passes, 12 unique query variants, 48 adapter queries, 15 records per adapter query, 4 concurrent jobs, and 180 seconds. These are resource ceilings, not search-depth modes. Provider responses may be truncated; coverage records that fact. Requests are rate-limited per host (GitHub: at least 6.2 seconds apart), with bounded retries, backoff, response size, and timeouts. Multiple running app instances have separate rate limiters.

## Evidence and language behavior

The seed is user-supplied. Legal-suffix spelling changes and mechanical transliterations are hypotheses. An exact textual match to a Wikidata label or alias can produce foreign-language search candidates, each linked to its source record and explicitly marked **discovered**, not confirmed. A matching label does not establish that a record describes the intended subject. Multiple URLs alone never promote a candidate to corroborated.

Language detection is conservative and leaves short names as `und` (undetermined). Provider-declared languages are retained. Multilingual labels and aliases are sourced from Wikidata in ten configured languages; availability depends on the matched records. Source text is never overwritten. A replaceable `TranslationBackend` protocol and translation-preservation helper are implemented and tested; **no machine-translation service is enabled by default**.

Correlation uses observed domains, DOI identifiers, repository names, Wikidata IDs, and exact email identifiers. It creates observation edges, not person-identity assertions. A shared hosting domain is not evidence of shared ownership. The UI exposes evidence relationships without imposing a graph dashboard.

Deduplication recognizes normalized URLs, exact substantial text hashes, and high text similarity. Duplicate records and their discovery paths remain stored. Short or empty metadata does not collapse unrelated records. Path case, trailing slash semantics, and repeated query-parameter order are preserved. Semantic translated-copy matching is not implemented.

Ranking is a transparent weighted sum: title token overlap (40), body overlap (25), exact title phrase (20), stable identifier (5), traceable provenance (5), and original record (5). Evidence completeness measures available source URL, discovery chain, original text, and date; it is **not a truth probability**. Provider reputation or independence is not assumed.

## Architecture

```text
tractor/
  app.py                 Desktop and headless entry points
  ui/                    Qt widgets and cancellable background worker
  core/                  Models, query plans, engine, provenance, scoring, convergence
  sources/               Common adapter contract and four complete API adapters
  language/              Detection, transliteration, translation protocol
  analysis/              Conservative identifier relationships
  network/               Pooling, retries, route isolation, throttling, robots helper
  storage/               SQLite migrations, atomic checkpoints, expiring response cache
  export/                JSON, CSV, and Markdown reports
tests/                   Mocked providers, engine, storage, network, and native UI checks
```

The GUI owns no networking logic. A QThread runs an asyncio engine and sends detached snapshots via Qt signals. Each owning thread has its own SQLite connection. The database uses WAL, parameterized queries, migrations, atomic checkpoints, complete JSON snapshots, and queryable record projections. Source payloads and translations are retained inside result records. Closing during retrieval cancels requests before the worker is destroyed.

### Adding a source

Implement `SourceAdapter.search(QueryVariant, SearchContext) -> SearchBatch`, provide a stable adapter ID/name/description, and register it in `sources.default_adapters()`. Official API hosts must also be registered in the explicit network allowlist. Return `SourceResult` objects and optional `QueryVariant` candidates with `parent_result`, reason, and evidence URLs. The engine requires no provider-specific branch. Supply mocked responses and contract tests.

Future page crawlers must obtain and enforce robots rules through an approved network context before fetching pages. A failed robots request is not permission. Current adapters use official metadata APIs and do not crawl arbitrary result URLs.

### Tor boundary

`network/tor.py` supplies a distinct Tor client using an explicit SOCKS proxy with remote DNS. Clearnet clients reject onion hosts; Tor clients reject clearnet hosts. Redirect destinations are validated before following. No Tor daemon is started, no onion index is configured, and no live onion adapter ships in this MVP. The seam is tested; live Tor behavior is not yet validated.

## Privacy and security

No telemetry, advertising, search-history upload, credential storage, or background network requests on startup. Search terms and discovered variants go to enabled providers when you search; those services can observe your IP and apply their own retention policies. Local investigations, cache, and exports are sensitive research data and are not encrypted by this application. Use OS account protections and disk encryption where needed.

Data defaults to the platform user-data location from `platformdirs` (`~/.local/share/TRACTOR` on typical Linux systems). Settings shows the exact location. Remove that directory while the app is closed to remove history, cache, and settings. Structured logs go to stderr and use query IDs rather than full queries; no credentials or raw provider error bodies are logged. `--debug` enables the application debug level without enabling HTTP wire logging.

Read [SECURITY.md](SECURITY.md) for retrieval boundaries and vulnerability reporting.

## Development and verification

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
QT_QPA_PLATFORM=offscreen pytest -q
python -m build
```

Tests block live HTTP connections and use mocked responses. GUI tests exercise real Qt widgets, queued worker signals, streaming, filtering, and reopened evidence. The GitHub Actions workflow targets Python 3.11, 3.12, and 3.13 on Linux. Live API checks are separate from deterministic tests.

## Next steps

This release is the requested vertical slice, not the entire long-term source catalog. Future work includes additional web/news/government/forum providers, source-specific pagination, richer entity extraction, evidence-backed geographic pivots, a configured translation service, public onion adapters, isolated full-document extraction (including PDF), semantic translated-copy detection, refresh scheduling, and signed native installers. No unsupported source family is represented as searched.

License: the repository's existing [AGPL-3.0 license](LICENSE).
