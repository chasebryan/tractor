# Security policy

TRACTOR discovers and correlates publicly accessible information. It does not implement intrusion, authentication bypass, exploitation, credential theft, malware execution, or operator deanonymization.

## Trust boundaries

All provider content is untrusted data. Result cards explicitly use Qt plain-text labels. Previews use read-only text widgets without an HTML or JavaScript engine. Metadata APIs accept at most 4 MiB of JSON; the Tor HTML path accepts at most 2 MiB of decoded text. HTML is parsed into plain-text snippets with Beautiful Soup; it never executes returned content, opens a binary, loads a remote image, or fetches a result URL automatically. The user can explicitly open an HTTP(S) source in an external browser, which applies its own policies.

The API client validates URLs and redirects against an explicit host allowlist, rejects URL credentials and nonstandard remote ports for built-in APIs, requires HTTPS for clearnet APIs, disables environment-provided proxies, and separates clearnet from Tor. An explicitly configured SearxNG server registers only its exact origin (scheme, host, and port); HTTP is permitted only for a loopback server. A configured server and its upstream search engines receive the user's queries. Changing servers does not silently reuse a saved page cursor against a different server. Tor uses `socks5h` for remote DNS, validates v3 onion checksums, and accepts only registered onion hosts on standard ports. Redirects cannot escape that context; there is no clearnet fallback. The built-in Torch index and an optional user-configured onion SearxNG server use this path. No retrieved result URL is fetched automatically. Onion links are shown for the user to open in Tor Browser, never passed automatically to the ordinary browser. Do not turn a provider-returned URL into a network target without an appropriate policy.

Torch retrieval checks robots.txt before submitting search terms, honors wildcard and query-string exclusions, and applies crawl delays and request rates. HTTP 404/410 means no policy is published; authentication errors, server errors, timeouts, and HTML masquerading as a policy stop the source. Standard hidden search-form fields are replayed only to the fixed search URL. No JavaScript is executed, and interactive challenges are not bypassed. Unrecognized pages are errors, not empty successful searches.

Tor startup is lazy and cancellable. Only local SOCKS proxies are configurable. A SOCKS greeting detects a proxy, not its anonymity properties; configured proxies are trusted. Automatic startup runs the installed `tor` executable directly without a shell, using a private application data directory, a loopback-only dynamically assigned SOCKS port, and no control listener. It neither downloads executables nor changes system services. Only a process started by this run is stopped on completion or cancellation. Ordinary provider queries still use the direct connection.

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
