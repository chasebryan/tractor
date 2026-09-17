# TRACTOR

**Global Intelligence Search · v0.2**

A native desktop application for evidence-led research across independent public sources. Enter one subject. The engine builds a query plan, retrieves successive result pages, follows traceable multilingual candidates, groups duplicate records, and saves the evidence and unfinished work on your device.

The launch screen has one wordmark and one search field. Results, source coverage, and evidence appear as the investigation runs. A completed run describes the recorded search scope; it does not imply exhaustive coverage of the internet.

## Download and run

[Download the application source](https://github.com/chasebryan/tractor/archive/refs/heads/tractor-mvp.zip), extract it, and install **Python 3.11–3.13** (3.12 recommended). The built-in providers require no API keys.

**Linux and macOS:** open a terminal in the extracted folder and run:

```bash
sh run.sh
```

**Windows:** double-click `run.cmd`. Install Python with its `py` launcher enabled.

The launcher creates a private `.venv` and installs dependencies on the first run. Later launches reuse it; dependency changes trigger installation again. First-time setup requires internet access. The desktop application makes no network requests until you start a search.

On Fedora, install a supported interpreter with `sudo dnf install python3.12`. The launcher also accepts Python 3.11 and 3.13; Python 3.14 is not supported by the Qt version used here. Qt 6.8 is pinned for older desktop CPU compatibility. Linux requires desktop graphics libraries; minimal systems may need EGL, OpenGL, and Qt xcb dependencies. Wayland is also supported. Linux has been exercised directly; Windows and macOS launchers need platform verification. Signed native installers are not included.

To clone or update the development branch:

```bash
git clone --branch tractor-mvp https://github.com/chasebryan/tractor.git
cd tractor
sh run.sh
```

For an existing checkout on that branch, run `git pull --ff-only`, then `sh run.sh` again.

Manual installation is also supported:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
tractor
```

On Windows, activate with `.venv\Scripts\Activate.ps1`.

## Use it

1. Enter a name, organization, or topic and press Enter. Every search uses the same iterative engine; there is no shallow-search mode.
2. Read results as sources respond. Cards show source category, provider, available date, language, relevance, and a link. Filtering and sorting work during retrieval. New arrivals retain existing cards and preserve the record you are reading.
3. Open **Evidence** to inspect the original text, discovery chain, ranking calculation, content hash, and provider metadata. **Related** shows observed identifiers and retained duplicates. **Copy link** copies the source address; **Open source** opens your external browser.
4. Open **Coverage** to inspect attempts, provider errors, request/cache counts, languages, discovery passes, limits, and the queue of remaining searches.
5. **Stop** cancels outstanding requests and saves collected evidence. **Continue** resumes the saved queue, including after closing and reopening the app. **Refresh** starts a separate investigation using fresh requests and preserves its predecessor in History.
6. Search **History** by subject or collected source text. Reopen an investigation to review or continue it. **Export** writes full JSON, Markdown, or spreadsheet-safe CSV.

Results can be filtered by text, category, provider, language, domain, publication date, source region, observed entity type, and relevance, or sorted by relevance/newest/oldest. Unknown dates sort last. Partial publication dates remain partial; date filters use their possible range. Provider-reported source country is not treated as the subject's location.

Shortcuts: **Ctrl+L** focuses the search, **Esc** stops retrieval, **Ctrl+E** exports, and **Ctrl+H** opens history when the engine is idle.

## Sources

| Provider | Coverage | Reference |
| --- | --- | --- |
| Wikidata | Knowledge records and multilingual labels; not an official company registry | [Wikibase API](https://www.mediawiki.org/wiki/Wikibase/API) |
| Crossref | Publication metadata, available abstracts, DOI identifiers | [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) |
| Internet Archive | Archived item catalog metadata; not a Wayback-wide crawl | [Internet Archive developer portal](https://archive.org/developers/) |
| GitHub | Public repository names and descriptions; not authenticated code search | [Repository search](https://docs.github.com/en/rest/search/search#search-repositories) |
| Europe PMC | Life-sciences publication metadata, abstracts, DOI and PubMed identifiers | [Europe PMC services](https://europepmc.org/RestfulWebService) |
| GDELT News | Recent global news article metadata, over a three-month window | [GDELT DOC API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) |
| SearxNG, optional | General web result snippets from your configured server | [SearxNG search API](https://docs.searxng.org/dev/search_api.html) |

Select providers in **Settings**. Desktop and command-line searches use the same saved selections. An unavailable or rate-limited source is reported as failed, while other providers keep running. Failure is never represented as zero matches. The latest live verification reached five of the six built-in services; GDELT timed out and was recorded as unavailable.

To enable general web search, enter a SearxNG server URL in Settings and select its checkbox. Use a server you operate or trust, with JSON output enabled. Many public instances disable JSON access. HTTPS is required except for a local loopback server such as `http://127.0.0.1:8080`. Queries also reach the upstream engines selected by that server. No public instance is selected automatically. Changing the configured server requires a fresh investigation for that source; saved cursors are not silently sent to a different server.

The built-in services do not form a general web index. News metadata is not full article text; GDELT's seen time is retained as an observation time, not invented as a publication date. Third-party coverage, availability, and indexing vary.

## Engine and evidence

**A persistent work queue.** Each unit records provider, query, discovery pass, page, and cursor. Successful pages are checkpointed into SQLite. Interrupted pages remain queued. Continuation retries unfinished work without repeating successful pages. A provider has at most one active search; other providers can run concurrently. Repeated pages and cursors stop with an explicit coverage note.

Each run permits up to 72 adapter searches, 3 pages per provider/query, 240 seconds, and 6 concurrent jobs. Investigations are bounded to 3 discovery passes, 12 query variants, and 3,000 retained records; each retrieval accepts up to 15 records. These are resource ceilings, not completeness claims. **Continue** renews the per-run page, query, and time budgets. The record cap remains investigation-wide. Provider-specific caps and unavailable pagination are disclosed. GitHub exposes at most 1,000 search hits; Crossref's offset retrieval is bounded at 10,000. GDELT does not paginate in this implementation.

Requests are rate-limited per host (GitHub: at least 6.2 seconds apart), with bounded retries, backoff, response sizes, caching, and connection/read timeouts. Multiple application instances have separate rate limiters. Refresh bypasses the saved HTTP cache.

**Traceable candidates.** The seed is user-supplied. Legal-suffix spelling changes and mechanical transliterations are hypotheses. An exact textual match to a Wikidata label can produce foreign-language candidates, each linked to a source and marked **discovered**, not confirmed. Matching names do not establish that a record describes the intended subject. Multiple URLs alone never promote an alias to corroborated. Discovery depth and variant limits appear in coverage notes.

Language detection leaves short names undetermined. Provider-declared languages are retained, with common Europe PMC language codes normalized. Multilingual Wikidata labels are requested in ten configured languages, independently of browser or OS locale. Original text is never overwritten. A tested `TranslationBackend` protocol is available for integrations; **no machine-translation service is enabled**.

**Duplicate grouping.** An index matches canonical URLs, stable identifiers such as DOI and PubMed IDs, exact substantial content hashes, and bounded near-text comparisons. Conflicting stable identifiers prevent text-only merging. Short or empty metadata does not collapse unrelated records. Duplicate copies and their discovery paths remain stored and exported. Near-text matches are marked as inferences. Semantic matching of translated copies is not implemented.

**Transparent ranking.** Relevance combines title token overlap (up to 35), body overlap (20), a whole-token title phrase (20), corpus-aware BM25 term rarity (15), provenance (5), and stable identifiers (5). A traceable candidate query can rank a foreign-language record; candidate lexical contributions receive a 15% discount. Evidence shows the actual query and components used. The score is not an identity assertion or truth probability. Evidence completeness separately measures the available URL, discovery chain, original text, and date.

**Conservative relationships.** Shared domains, DOI, PubMed and Wikidata IDs, repository names, and exact email identifiers create observation edges. Shared hosting does not establish shared ownership, and shared names do not establish person identity. The evidence graph remains inspectable without imposing a graph dashboard.

## Command line

The same engine runs without opening Qt windows:

```bash
tractor --search "OpenStreetMap" --export-json investigation.json
tractor --history
tractor --history "cartography"
tractor --resume INVESTIGATION_ID --export-json continued.json
tractor --search "OpenStreetMap" --sources wikidata crossref europe_pmc
```

From a launcher installation, replace `tractor` with `.venv/bin/tractor` on Linux/macOS or `.venv\Scripts\tractor.exe` on Windows. Alternatively, pass the same options to `sh run.sh` or `run.cmd`. Use `--data-dir ./local-investigations` to select a different local store. `--sources` overrides the saved choices for that command. Ctrl+C checkpoints collected results and remaining work.

## Storage, exports, and privacy

SQLite stores atomic investigation snapshots, individual record projections, cached responses, and a local full-text history index. Existing v0.1 history migrates automatically. Older investigations without saved cursors can be reopened and refreshed. A stopped application leaves unfinished investigations visibly marked as interrupted.

JSON preserves results, duplicates, source payloads, query states, entities, edges, attempts, budgets, source configuration, and remaining tasks. Markdown includes sources, coverage, trails, attempts, and limits. CSV includes every retained result with a duplicate reference and neutralizes spreadsheet formulas. Exports are atomically replaced only after a complete write.

No telemetry, advertising, history upload, stored API credentials, or background searching. Search terms and discovered variants go to enabled providers; those services can observe your IP and apply their own policies. Investigations, cache, and exports are stored unencrypted. Default data location comes from `platformdirs` (`~/.local/share/TRACTOR` on typical Linux systems); Settings shows the exact location. Remove that directory while the app is closed to delete history, cache, and settings. Structured logs use query IDs rather than full queries or raw provider error bodies.

Read [SECURITY.md](SECURITY.md) for retrieval boundaries and reporting.

## Architecture and development

```text
tractor/
  app.py                 Desktop and headless entry points
  settings.py            Shared provider configuration
  ui/                    Qt widgets and cancellable background worker
  core/                  Queue, models, provenance, deduplication, ranking, filters
  sources/               Six public API adapters and optional SearxNG integration
  language/              Detection, transliteration, translation protocol
  analysis/              Observed identifier relationships
  network/               Pooling, retries, route isolation, throttling, robots helper
  storage/               SQLite migrations, full-text history, cache, atomic file writes
  export/                JSON, CSV, and Markdown reports
scripts/launch.py         First-run environment setup
```

The GUI owns no networking logic. A QThread runs an asyncio engine and sends detached snapshots via Qt signals. Each thread has its own SQLite connection. Closing during retrieval cancels requests before the worker is destroyed.

To add a source, implement `search(QueryVariant, SearchContext) -> SearchBatch` and register the adapter. Return normalized `SourceResult` objects, optional evidence-backed query candidates, and a `next_cursor` for pagination. Official API hosts must be registered in the network policy. The scheduler requires no provider-specific branches. Add mocked contract and pagination tests.

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
QT_QPA_PLATFORM=offscreen pytest -q
python -m build
```

Deterministic tests block live HTTP and exercise provider contracts, pagination, continuation, cancellation, provenance, ranking, deduplication, network boundaries, migrations, exports, and real Qt widgets. CI targets Python 3.11, 3.12, and 3.13 on Linux. Live-service checks are separate.

A distinct Tor client supports explicit SOCKS routing with remote DNS and rejects clearnet destinations. No daemon is started and no live onion adapter is included; live Tor behavior remains unverified. Full-document/PDF extraction, scheduled refresh, translation service integration, additional government/forum sources, and signed installers are future work. Current adapters use metadata/search APIs and do not crawl arbitrary result pages. Future crawlers must enforce robots policies and bound document parsing resources.

License: [AGPL-3.0](LICENSE).
