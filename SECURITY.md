# Security policy

TRACTOR discovers and correlates publicly accessible information. It does not implement intrusion, authentication bypass, exploitation, credential theft, malware execution, or operator deanonymization.

## Trust boundaries

All provider content is untrusted data. Result cards explicitly use Qt plain-text labels. Previews use read-only text widgets without an HTML or JavaScript engine. The metadata API client only accepts bounded JSON; it never executes returned content, opens a binary, loads a remote image, or fetches a result URL automatically. The user can explicitly open an HTTP(S) source in an external browser, which applies its own policies.

The API client validates URLs and redirects against an explicit host allowlist, rejects URL credentials and nonstandard remote ports for built-in APIs, requires HTTPS for clearnet APIs, disables environment-provided proxies, and separates clearnet from Tor. An explicitly configured SearxNG server registers only its exact origin (scheme, host, and port); HTTP is permitted only for a loopback server. A configured server and its upstream search engines receive the user's queries. Changing servers does not silently reuse a saved page cursor against a different server. Tor uses `socks5h` for remote DNS and accepts only registered onion hosts. There are no live onion providers in this release. Do not turn a provider-returned URL into a network target without an appropriate policy.

SQLite queries are parameterized. Source content cannot choose local filenames or filesystem paths. Export destinations are chosen by the user. Markdown escapes source text; CSV neutralizes formula-leading cells. JSON is data, not an instruction format. No retrieved code is evaluated, imported, executed, or passed to a shell.

Rate limits, deadlines, concurrency limits, pass/query limits, bounded responses, and cache expiry limit resource use. Near-duplicate matching is bounded to the initial text segment. Future PDF/document parsers should run with process-level resource constraints before accepting downloads. Current adapters retain publication or catalog metadata rather than extracting full documents.

The local database and cache are unencrypted. Exports include investigation queries and source material. The app stores no API credentials and does not log full queries or provider error bodies. Provider authors must not place credentials in result metadata, exception messages, or logging fields.

## Changes requiring special review

- Network hosts, proxy behavior, redirects, or onion adapters.
- Page crawlers and robots.txt failure behavior.
- Rich-text/HTML rendering, automatic link opening, or embedded browsers.
- Document parsers and file downloads.
- Credential storage, telemetry, synchronization, and third-party translation.
- Entity identity claims and automatic alias corroboration.

Source adapters are trusted application code, not a sandbox. Review plugins before installation. Automated tests use mocked HTTP transports and exercise routing, rendering, cancellation, export, and provenance boundaries.

## Reporting a vulnerability

Use private GitHub vulnerability reporting if the repository owner has enabled it. Otherwise contact the maintainer privately through a channel listed on their GitHub profile. Do not publish credentials, personal investigation data, or an unredacted exploit in a public issue. Include the affected version, reproduction steps, trust boundary crossed, and expected behavior.
