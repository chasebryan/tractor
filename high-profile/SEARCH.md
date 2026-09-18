# Search

The primary index searches published claim statements with entity names, aliases and country context. PostgreSQL `plainto_tsquery` handles literal terms with both English stemming and a language-neutral dictionary. Exact name/alias matching supports text outside English. User values are always bound parameters. Wildcard characters are escaped for substring fallbacks.

Profiles can also be searched independently through `/api/entities?q=...`, and bibliographic sources through `/api/sources?q=...`.

## Structured filters

`country`, `kind`, `classification`, `confidence`, `publisher`, `source`, `region`, `min_evidence`, `since`, `until`, `as_of`, `known_at`, `disputed`, `changed`, `synthetic`, `page`, `limit`.

Country values are two-letter codes. Dates are valid ISO calendar dates. `min_evidence` counts supporting fragments; independent publisher groups are reported separately. `changed=true` selects a latest eligible revision after version 1. `synthetic=false` removes scenario claims. Results preserve original-source references, publication dates, retrieval dates, source lifecycle and support/contradiction roles.

Default page size is 30; maximum is 100. Stable secondary ordering makes pagination repeatable. Unknown parameters, impossible dates and invalid enum values return HTTP 400 rather than silently falling back.

## Natural-language interpretation

The current deterministic grammar recognizes queries starting with **show**, **find**, **which** or **list**, selected country names, **since YEAR**, **documented**, **changes**, and **disagreements**. It emits the inferred filters and retains unrecognized text as literal keywords. The UI exposes this interpretation.

Example: `Show changes to China's nuclear capabilities since 2015` becomes country CN, changed true, since 2015-01-01. Adding `documented` applies that classification; no matches is a valid result because the seed's relevant claim is ASSESSED.

The interpreter does not reason over arbitrary geopolitical questions, infer an absence of capability, execute generated SQL or use an LLM. Complex questions outside its grammar should be expressed with visible filters. Treaty-status comparisons, advanced quantitative estimate comparisons and free-form semantic retrieval are later capabilities.

## Historical queries

`as_of` is a reconstruction of public availability and effective dates; it does not simulate what the application knew at an earlier date. `known_at` adds the separate knowledge cutoff. Source lifecycle describes the retained source record; a current lifecycle notice is not retroactively asserted to have existed at the reconstruction date.
