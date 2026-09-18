import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  Command,
  Database,
  Download,
  ExternalLink,
  FileText,
  Filter,
  FolderOpen,
  History,
  Link2,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, date, label, useApi } from "./api";

import {
  Badge,
  ClaimList,
  Empty,
  PageTitle,
  SearchBox,
  Status,
  Timeline,
} from "./components";
import { useActions } from "./context";
function CountryGrid() {
  const { data, error } = useApi("/api/countries");
  return (
    <Status data={data} error={error}>
      <div className="country-grid">
        {data?.items.map((c: any) => (
          <Link key={c.id} to={`/profiles/${c.slug}`} className="country-card">
            <span className="country-code">{c.country_code}</span>
            <div>
              <h3>{c.name}</h3>
              <span>{c.broad_location}</span>
            </div>
            <ArrowUpRight size={18} />
          </Link>
        ))}
      </div>
    </Status>
  );
}
export function Home() {
  const { data: meta } = useApi("/api/meta");
  const { data, error } = useApi("/api/search?limit=6&synthetic=false");
  const [tab, setTab] = useState("evidence");
  return (
    <>
      <div className="home-heading">
        <div className="eyebrow">
          <span className="tiny-square" /> HIGH-PROFILE INDEX{" "}
          <span className="separator">/</span> PUBLIC-SOURCE RESEARCH
        </div>
        <h1>Start with the evidence.</h1>
        <p>Global Nuclear Capabilities Intelligence</p>
      </div>
      <SearchBox large />
      <div className="suggestions">
        <span>EXPLORE</span>
        {["China", "Barakah", "French airborne component"].map((q) => (
          <Link key={q} to={`/search?q=${encodeURIComponent(q)}`}>
            {q}
            <ArrowUpRight size={12} />
          </Link>
        ))}
        <Link to="/search?disputed=true">
          Conflicting claims
          <ArrowUpRight size={12} />
        </Link>
      </div>
      <div className="index-summary">
        {[
          ["entities", "Indexed entities"],
          ["claims", "Cited claims"],
          ["sources", "Source documents"],
          ["countries", "Country profiles"],
        ].map(([key, title]) => (
          <div key={key}>
            <strong>{String(meta?.counts[key] ?? "—").padStart(2, "0")}</strong>
            <span>{title}</span>
          </div>
        ))}
        <div className="summary-note">
          <ShieldCheck size={20} />
          <span>
            Every claim has evidence.
            <br />
            Every change has a history.
          </span>
        </div>
      </div>
      <div className="home-content">
        <section className="primary-section">
          <div className="section-tabs">
            <button
              className={tab === "evidence" ? "active" : ""}
              onClick={() => setTab("evidence")}
            >
              Recent evidence
            </button>
            <button
              className={tab === "countries" ? "active" : ""}
              onClick={() => setTab("countries")}
            >
              Country profiles
            </button>
            <Link
              to={tab === "countries" ? "/directory?kind=COUNTRY" : "/search"}
            >
              View index <ArrowUpRight size={14} />
            </Link>
          </div>
          {tab === "evidence" ? (
            <Status data={data} error={error}>
              <ClaimList items={data?.items ?? []} compact />
            </Status>
          ) : (
            <CountryGrid />
          )}
        </section>
        <aside className="research-aside">
          <div className="eyebrow">
            COLLECTION NOTE <span>01</span>
          </div>
          <h2>
            Evidence, with its
            <br />
            uncertainty intact.
          </h2>
          <p>
            This development collection brings together selected public
            references from 1970–2025. It is not a current global assessment.
          </p>
          <Link to="/methodology" className="text-link">
            Read the methodology <ArrowRight size={15} />
          </Link>
          <div className="aside-divider" />
          <div className="eyebrow">IN FOCUS</div>
          <Link to="/profiles/china-program" className="focus-link">
            <span>Assessment history</span>
            <h3>How an assessment changes</h3>
            <p>
              Follow successive public assessments of China’s nuclear programme.
            </p>
            <ArrowUpRight size={18} />
          </Link>
          <Link to="/profiles/review-scenario" className="focus-link">
            <span className="amber-text">SYNTHETIC REVIEW CASE</span>
            <h3>When sources disagree</h3>
            <p>Inspect opposing claims without losing either evidence chain.</p>
            <ArrowUpRight size={18} />
          </Link>
        </aside>
      </div>
      <div className="collection-banner">
        <Database size={17} />
        <span>
          <strong>Development reference collection</strong> · Historical public
          references and explicitly marked synthetic scenarios. No automated
          source monitoring is active.
        </span>
        <Link to="/sources">
          Open Source Ledger
          <ArrowUpRight size={14} />
        </Link>
      </div>
    </>
  );
}
const classOptions = [
  "DOCUMENTED",
  "OFFICIALLY_STATED",
  "ASSESSED",
  "ESTIMATED",
  "REPORTED",
  "DISPUTED",
  "UNVERIFIED",
  "HISTORICAL",
  "SUPERSEDED",
  "RETRACTED",
];
const kindOptions = [
  "COUNTRY",
  "PROGRAM",
  "FACILITY",
  "REACTOR",
  "ORGANIZATION",
  "DELIVERY_SYSTEM",
  "WEAPON_SYSTEM",
  "TREATY",
  "AGREEMENT",
  "EVENT",
  "FUEL_CYCLE_CAPABILITY",
];
export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const filters = new URLSearchParams(params);
  filters.delete("claim");
  filters.delete("version");
  const { data, error } = useApi(`/api/search?${filters}`);
  const { data: meta } = useApi("/api/meta");
  const [advanced, setAdvanced] = useState(false);
  const update = (key: string, value: string) => {
    setParams((old) => {
      const p = new URLSearchParams(old);
      value ? p.set(key, value) : p.delete(key);
      p.delete("page");
      return p;
    });
  };
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH / SEARCH"
        title="Evidence index"
        description="Search the public record. Inspect the claim behind every result."
      />
      <SearchBox initial={params.get("q") ?? ""} />
      <div className="filterbar">
        <span className="filter-label">
          <Filter size={15} /> Refine
        </span>
        <select
          aria-label="Filter country"
          value={params.get("country") ?? ""}
          onChange={(e) => update("country", e.target.value)}
        >
          <option value="">All countries</option>
          {meta?.countries.map((c: any) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter entity type"
          value={params.get("kind") ?? ""}
          onChange={(e) => update("kind", e.target.value)}
        >
          <option value="">All entity types</option>
          {kindOptions.map((k) => (
            <option key={k} value={k}>
              {label(k)}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter classification"
          value={params.get("classification") ?? ""}
          onChange={(e) => update("classification", e.target.value)}
        >
          <option value="">All classifications</option>
          {classOptions.map((k) => (
            <option key={k} value={k}>
              {label(k)}
            </option>
          ))}
        </select>
        <button
          className={advanced ? "active" : ""}
          onClick={() => setAdvanced(!advanced)}
          aria-expanded={advanced}
        >
          <SlidersHorizontal size={15} /> More filters
        </button>
        <button
          className="reset"
          onClick={() =>
            setParams(params.get("q") ? { q: params.get("q")! } : {})
          }
        >
          Reset
        </button>
      </div>
      {advanced && (
        <div className="advanced-filters">
          <label>
            Confidence
            <select
              value={params.get("confidence") ?? ""}
              onChange={(e) => update("confidence", e.target.value)}
            >
              <option value="">All confidence levels</option>
              {["VERY HIGH", "HIGH", "MODERATE", "LOW", "INSUFFICIENT"].map(
                (c) => (
                  <option key={c}>{c}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Publisher
            <select
              value={params.get("publisher") ?? ""}
              onChange={(e) => update("publisher", e.target.value)}
            >
              <option value="">All publishers</option>
              {meta?.publishers.map((p: any) => (
                <option key={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label>
            Public evidence as of
            <input
              type="date"
              value={params.get("as_of") ?? ""}
              onChange={(e) => update("as_of", e.target.value)}
            />
          </label>
          <label>
            Published since
            <input
              type="date"
              value={params.get("since") ?? ""}
              onChange={(e) => update("since", e.target.value)}
            />
          </label>
          <label>
            Minimum supporting fragments
            <input
              type="number"
              min="0"
              max="100"
              value={params.get("min_evidence") ?? ""}
              onChange={(e) => update("min_evidence", e.target.value)}
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={params.get("disputed") === "true"}
              onChange={(e) =>
                update("disputed", e.target.checked ? "true" : "")
              }
            />
            Contradictory evidence only
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={params.get("synthetic") !== "false"}
              onChange={(e) =>
                update("synthetic", e.target.checked ? "" : "false")
              }
            />
            Include synthetic scenarios
          </label>
        </div>
      )}
      <div className="results-meta">
        <span>
          <strong>{data?.total ?? "—"}</strong> cited claims
        </span>
        <span>PUBLIC RECORD · RELEVANT SOURCE DATES RETAINED</span>
      </div>
      {data?.interpreted.interpretation.length > 0 && (
        <details className="query-explanation">
          <summary>
            <Command size={14} /> Interpreted search <ChevronDown size={14} />
          </summary>
          <div>
            {data.interpreted.interpretation.map((t: string) => (
              <code key={t}>{t}</code>
            ))}
            {data.interpreted.notice && <p>{data.interpreted.notice}</p>}
          </div>
        </details>
      )}
      <Status data={data} error={error}>
        <ClaimList items={data?.items ?? []} />
      </Status>
      {data && data.total > data.limit && (
        <div className="pagination">
          <button
            className="button"
            disabled={data.page === 1}
            onClick={() =>
              setParams((old) => {
                old.set("page", String(data.page - 1));
                return old;
              })
            }
          >
            Previous
          </button>
          <span>
            Page {data.page} of {Math.ceil(data.total / data.limit)}
          </span>
          <button
            className="button"
            disabled={data.page * data.limit >= data.total}
            onClick={() =>
              setParams((old) => {
                old.set("page", String(data.page + 1));
                return old;
              })
            }
          >
            Next
          </button>
        </div>
      )}
    </>
  );
}
export function Directory() {
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") ?? "";
  const { data, error } = useApi(`/api/entities${kind ? `?kind=${kind}` : ""}`);
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH / PROFILES"
        title={kind === "COUNTRY" ? "Country profiles" : "Entity directory"}
        description="Navigate countries, programmes, facilities and their evidence relationships."
      />
      <div className="directory-tabs">
        <button onClick={() => setParams({})} className={!kind ? "active" : ""}>
          All entities
        </button>
        {["COUNTRY", "PROGRAM", "FACILITY", "DELIVERY_SYSTEM", "TREATY"].map(
          (k) => (
            <button
              className={kind === k ? "active" : ""}
              key={k}
              onClick={() => setParams({ kind: k })}
            >
              {label(k)}
            </button>
          ),
        )}
      </div>
      <Status data={data} error={error}>
        <div className="entity-grid">
          {data?.items.map((e: any) => (
            <Link key={e.id} to={`/profiles/${e.slug}`} className="entity-card">
              <div className="entity-card-top">
                <span>{e.country_code ?? "INT"}</span>
                <Badge value={e.kind} muted />
              </div>
              <h2>
                {e.name}
                <ArrowUpRight size={17} />
              </h2>
              <p>{e.description}</p>
              <div className="entity-card-foot">
                {e.is_synthetic ? (
                  <span className="synthetic">SYNTHETIC SCENARIO</span>
                ) : (
                  <span>{e.country_name ?? "International"}</span>
                )}
                <span>{e.claim_count} claims</span>
              </div>
            </Link>
          ))}
        </div>
      </Status>
    </>
  );
}
export function Profile() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("claims");
  const cutoff = params.get("as_of") ?? "";
  const { data, error } = useApi(
    `/api/entities/${id}${cutoff ? `?as_of=${cutoff}` : ""}`,
  );
  const timeline = useApi(data ? `/api/timeline?entity=${data.id}` : null);
  useEffect(() => setTab("claims"), [id]);
  const sourceMap = new Map<string, any>();
  data?.claims.forEach((c: any) =>
    c.provenance.forEach((s: any) => sourceMap.set(s.id, s)),
  );
  return (
    <Status data={data} error={error}>
      {data && (
        <>
          <div className="breadcrumb">
            <Link to="/directory">Index</Link>
            <ChevronRight size={13} />
            {label(data.kind)}
            <ChevronRight size={13} />
            {data.name}
          </div>
          <div className="dossier-heading">
            <div className="dossier-mark">{data.country_code ?? "INT"}</div>
            <div>
              <div className="eyebrow">
                HIGH-PROFILE / {label(data.kind)}{" "}
                {data.is_synthetic && (
                  <span className="synthetic">SYNTHETIC SCENARIO</span>
                )}
              </div>
              <h1>{data.name}</h1>
              <div className="dossier-meta">
                <span>{data.broad_location ?? "Global"}</span>
                {data.aliases.map((a: any) => (
                  <span key={a.alias} lang={a.language}>
                    {a.alias}
                  </span>
                ))}
                <span>{data.claims.length} claims in this view</span>
              </div>
            </div>
          </div>
          <p className="profile-description">{data.description}</p>
          <div className="temporal-bar">
            <History size={17} />
            <label>
              Public evidence as of{" "}
              <input
                aria-label="Public evidence as of"
                type="date"
                value={cutoff}
                onChange={(e) =>
                  setParams((old) => {
                    e.target.value
                      ? old.set("as_of", e.target.value)
                      : old.delete("as_of");
                    return old;
                  })
                }
              />
            </label>
            {cutoff && (
              <button onClick={() => setParams({})}>Clear date</button>
            )}
            <span>
              Reconstructed from publication dates. Ingestion dates are
              preserved separately.
            </span>
          </div>
          <div className="section-tabs profile-tabs">
            {["claims", "relationships", "timeline", "sources"].map((t) => (
              <button
                key={t}
                className={tab === t ? "active" : ""}
                onClick={() => setTab(t)}
              >
                {label(t)}
                {t === "claims" && (
                  <span className="tab-count">{data.claims.length}</span>
                )}
              </button>
            ))}
          </div>
          {tab === "claims" && <ClaimList items={data.claims} />}{" "}
          {tab === "relationships" &&
            (data.relationships.length ? (
              <div className="relationship-list">
                {data.relationships.map((r: any) => (
                  <div key={r.id}>
                    <Link to={`/profiles/${r.subject_slug}`}>
                      {r.subject_name}
                    </Link>
                    <span>
                      <Link2 size={14} />
                      {r.predicate.replaceAll("_", " ")}
                    </span>
                    <Link to={`/profiles/${r.object_slug}`}>
                      {r.object_name}
                      <ArrowUpRight size={15} />
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <Empty
                title="No relationships in this view"
                text="The collection does not yet contain a supported relationship for this entity and date."
              />
            ))}
          {tab === "timeline" && (
            <Status data={timeline.data} error={timeline.error}>
              <Timeline
                items={(timeline.data?.items ?? []).filter(
                  (v: any) =>
                    !cutoff || String(v.public_on).slice(0, 10) <= cutoff,
                )}
              />
            </Status>
          )}
          {tab === "sources" && (
            <div className="source-cards">
              {[...sourceMap.values()].map((s) => (
                <Link to={`/sources/${s.id}`} key={s.id}>
                  <div>
                    <span className="eyebrow">{s.publisher}</span>
                    <h3>{s.title}</h3>
                    <p>Published {date(s.published_on)}</p>
                  </div>
                  <Badge value={s.health} />
                  <ArrowUpRight size={18} />
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </Status>
  );
}
export function Sources() {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const { data, error } = useApi(`/api/sources?${params}`);
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH / SOURCES"
        title="Source Ledger"
        description="The documents behind the assessments. Publisher, provenance and lifecycle in one record."
      />
      <form
        className="ledger-search"
        onSubmit={(e) => {
          e.preventDefault();
          setParams((old) => {
            text ? old.set("q", text) : old.delete("q");
            return old;
          });
        }}
      >
        <Search size={19} />
        <input
          aria-label="Search source ledger"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search documents or publishers…"
        />
        <button type="submit" className="button dark">
          Search
        </button>
      </form>
      <div className="filterbar">
        <span className="filter-label">
          <Filter size={15} /> Refine
        </span>
        <select
          aria-label="Source health"
          value={params.get("health") ?? ""}
          onChange={(e) =>
            setParams((old) => {
              e.target.value
                ? old.set("health", e.target.value)
                : old.delete("health");
              return old;
            })
          }
        >
          <option value="">All source health</option>
          {[
            "ACTIVE",
            "STALE",
            "ARCHIVED",
            "SUPERSEDED",
            "UNKNOWN",
            "DISCONTINUED",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Source language"
          value={params.get("language") ?? ""}
          onChange={(e) =>
            setParams((old) => {
              e.target.value
                ? old.set("language", e.target.value)
                : old.delete("language");
              return old;
            })
          }
        >
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="fr">French</option>
        </select>
        <span className="filter-count">
          {data?.items.length ?? "—"} documents
        </span>
      </div>
      <Status data={data} error={error}>
        {data?.items.length ? (
          <div className="ledger-table">
            <div className="ledger-head">
              <span>PUBLISHER / DOCUMENT</span>
              <span>PUBLISHED</span>
              <span>LANGUAGE</span>
              <span>HEALTH</span>
              <span>CLAIMS</span>
            </div>
            {data.items.map((s: any) => (
              <Link to={`/sources/${s.id}`} className="ledger-row" key={s.id}>
                <div>
                  <div className="claim-kicker">
                    {s.publisher}
                    <span>TIER {s.tier}</span>
                    {s.is_synthetic && (
                      <span className="synthetic">SYNTHETIC</span>
                    )}
                  </div>
                  <h3>
                    {s.title}
                    <ArrowUpRight size={15} />
                  </h3>
                  <small>Retrieved {date(s.retrieved_at)}</small>
                </div>
                <span>{date(s.published_on)}</span>
                <span className="mono">{s.language.toUpperCase()}</span>
                <Badge value={s.health} />
                <span>
                  {s.claims_supported} supporting
                  {s.claims_contradicted > 0 && (
                    <small className="amber-text">
                      {s.claims_contradicted} contradicting
                    </small>
                  )}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <Empty title="No source documents found" />
        )}
      </Status>
    </>
  );
}
export function SourceDetail() {
  const { id } = useParams();
  const { data, error } = useApi(`/api/sources/${id}`);
  return (
    <Status data={data} error={error}>
      {data && (
        <>
          <div className="breadcrumb">
            <Link to="/sources">Source Ledger</Link>
            <ChevronRight size={13} />
            {data.publisher}
          </div>
          <PageTitle
            eyebrow={`${data.publisher} / TIER ${data.tier}`}
            title={data.title}
            action={<Badge value={data.health} />}
          />
          {data.is_synthetic && (
            <div className="notice">
              Synthetic document. No external publisher or real-world claim is
              represented.
            </div>
          )}
          <div className="source-metadata">
            <div>
              <span>Publication date</span>
              <strong>{date(data.published_on)}</strong>
            </div>
            <div>
              <span>Original language</span>
              <strong>{data.language.toUpperCase()}</strong>
            </div>
            <div>
              <span>Document type</span>
              <strong>{data.document_type}</strong>
            </div>
            <div>
              <span>Dataset version</span>
              <strong>{data.dataset_version}</strong>
            </div>
          </div>
          <div className="source-notes">
            <p>{data.publisher_notes}</p>
            <p>{data.license}</p>
            <p>{data.archival_status}</p>
            {!data.is_synthetic && (
              <a
                className="button dark"
                href={data.canonical_url}
                target="_blank"
                rel="noreferrer"
              >
                Open original source
                <ExternalLink size={15} />
              </a>
            )}
          </div>
          <h2 className="section-title">Retrieval records</h2>
          {data.snapshots.map((s: any) => (
            <details className="retrieval" key={s.id}>
              <summary>
                {date(s.retrieved_at)} · {s.method} <ChevronDown size={15} />
              </summary>
              <p>{s.retrieval_note}</p>
              <p>{s.hash_scope}</p>
              <code>SHA-256: {s.content_hash}</code>
            </details>
          ))}
          <h2 className="section-title">Associated claims</h2>
          <ClaimList items={data.claims} />
        </>
      )}
    </Status>
  );
}
export function Watch() {
  const { data, error } = useApi("/api/watch");
  const { inspect } = useActions();
  return (
    <>
      <PageTitle
        eyebrow="HIGH-PROFILE / WATCH"
        title="Information changes"
        description="An append-only record of claims added and assessments revised."
      />
      <div className="notice">
        <Activity size={17} /> This is the local record-change log. Scheduled
        source monitoring and automated discovery are not active.
      </div>
      <Status data={data} error={error}>
        <div className="watch-list">
          {data?.items.map((w: any) => (
            <article key={w.id}>
              <div className="watch-icon">
                {w.type === "ASSESSMENT_REVISED" ? (
                  <History size={19} />
                ) : (
                  <FileText size={19} />
                )}
              </div>
              <div>
                <div className="claim-kicker">
                  {label(w.type)}
                  <span>·</span>
                  <Link to={`/profiles/${w.entity_slug}`}>{w.entity_name}</Link>
                  {w.is_synthetic && (
                    <span className="synthetic">SYNTHETIC</span>
                  )}
                </div>
                <button
                  className="claim-statement"
                  onClick={() => inspect(w.claim_id, w.version)}
                >
                  {w.description}
                </button>
                <small>
                  Recorded {date(w.occurred_at)} · source public{" "}
                  {date(w.public_on)} · effective {date(w.effective_from)}
                </small>
              </div>
              <ArrowUpRight size={17} />
            </article>
          ))}
        </div>
      </Status>
    </>
  );
}
export function Investigations() {
  const { data, error, reload } = useApi("/api/investigations");
  const [creating, setCreating] = useState(false),
    [title, setTitle] = useState(""),
    [description, setDescription] = useState(""),
    [saving, setSaving] = useState(false);
  const { notify } = useActions();
  async function create(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api("/api/investigations", {
        method: "POST",
        body: JSON.stringify({ title, description }),
      });
      setCreating(false);
      setTitle("");
      setDescription("");
      reload();
      notify("Investigation created. Open a claim to save evidence.");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="HIGH-PROFILE / RESEARCH"
        title="Investigations"
        description="Save exact claim versions, retain your notes, and export a cited evidence collection."
        action={
          <button
            className="button dark"
            onClick={() => setCreating(!creating)}
          >
            <Plus size={16} />
            New investigation
          </button>
        }
      />
      {creating && (
        <form className="investigation-form" onSubmit={create}>
          <label>
            Title
            <input
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Research question or topic"
              autoFocus
            />
          </label>
          <label>
            Description
            <textarea
              maxLength={4000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <div>
            <button className="button dark" disabled={saving}>
              {saving ? "Creating…" : "Create investigation"}
            </button>
            <button
              type="button"
              className="button"
              onClick={() => setCreating(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      <Status data={data} error={error}>
        {data?.items.length ? (
          <div className="entity-grid">
            {data.items.map((i: any) => (
              <Link
                key={i.id}
                className="entity-card"
                to={`/investigations/${i.id}`}
              >
                <div className="entity-card-top">
                  <FolderOpen size={22} />
                  <span>{i.item_count} saved claims</span>
                </div>
                <h2>
                  {i.title}
                  <ArrowUpRight size={17} />
                </h2>
                <p>{i.description || "No description added."}</p>
                <div className="entity-card-foot">
                  Updated {date(i.updated_at)}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <Empty
            title="A workspace for your research"
            text="Create an investigation, then save claims from the evidence inspector. Saved versions remain pinned when assessments change."
          />
        )}
      </Status>
    </>
  );
}
export function Investigation() {
  const { id } = useParams();
  const { data, error } = useApi(`/api/investigations/${id}`);
  const { inspect } = useActions();
  return (
    <Status data={data} error={error}>
      {data && (
        <>
          <div className="breadcrumb">
            <Link to="/investigations">Investigations</Link>
            <ChevronRight size={13} />
            Research collection
          </div>
          <PageTitle
            eyebrow="SAVED INVESTIGATION"
            title={data.title}
            description={data.description}
            action={
              <a
                href={`/api/investigations/${id}/export`}
                className="button dark"
                download
              >
                <Download size={16} />
                Export cited report
              </a>
            }
          />
          <div className="notice">
            Claims are saved as exact versions. Later revisions do not replace
            your research snapshot.
          </div>
          {data.items.length ? (
            <div className="saved-items">
              {data.items.map((item: any) => (
                <article key={item.id}>
                  <div className="claim-kicker">
                    {item.entity_name}
                    <Badge value={item.classification} />
                  </div>
                  <button
                    className="claim-statement"
                    onClick={() => inspect(item.claim_id, item.version)}
                  >
                    {item.statement}
                  </button>
                  <p>{item.note || "No analyst note."}</p>
                  <small>
                    Public {date(item.public_on)} · saved{" "}
                    {date(item.created_at)} · pinned version{" "}
                    {item.version_id.slice(0, 8)}
                  </small>
                </article>
              ))}
            </div>
          ) : (
            <Empty
              title="No claims saved yet"
              text="Search the index, open an evidence inspector and choose “Save to investigation”."
            />
          )}
        </>
      )}
    </Status>
  );
}
export function Methodology() {
  const { data, error } = useApi("/api/integrity");
  return (
    <>
      <PageTitle
        eyebrow="HIGH-PROFILE / METHODOLOGY"
        title="Every claim has a record."
        description="How to read this collection, evaluate confidence and follow the evidence."
      />
      <div className="method-grid">
        <section>
          <h2>Evidence before assessment</h2>
          <p>
            A published claim links to an evidence fragment, its original
            source, a publisher and a retrieval record. Source passages and
            editorial paraphrases are labeled separately. A generated assertion
            is never a source.
          </p>
          <h2>Classification ≠ confidence</h2>
          <p>
            “Officially stated” means an authority made a statement. “Estimated”
            identifies an estimate. Confidence explains the strength and
            limitations of that attribution through explicit factors, not a
            percentage.
          </p>
          <h2>Three different clocks</h2>
          <p>
            Effective dates describe the subject of a claim. Publication dates
            describe when evidence became public. Ingestion dates describe when
            HIGH-PROFILE recorded it. Historical filters reconstruct public
            availability; they do not pretend the system existed earlier.
          </p>
          <h2>Disagreement stays visible</h2>
          <p>
            Opposing evidence is retained beside supporting evidence. Multiple
            documents from a shared publisher group are not counted as
            independent corroboration. The included conflict scenario is
            entirely synthetic.
          </p>
        </section>
        <aside>
          <h2>Collection scope</h2>
          <p>
            Selected, manually reviewed references from SIPRI, ENEC, the French
            presidency and the UN Treaty Collection. This is development seed
            data, not comprehensive or current intelligence.
          </p>
          <h2>Research boundaries</h2>
          <p>
            Broad geography only. No precise military locations, live movements,
            vulnerabilities, targeting scores, weapon effects or operational
            planning.
          </p>
          <h2>Integrity checks</h2>
          <Status data={data} error={error}>
            {data && (
              <>
                <div className={`integrity-status ${data.ok ? "" : "error"}`}>
                  <ShieldCheck />
                  {data.ok
                    ? "Provenance checks passed"
                    : "Integrity issues found"}
                </div>
                <p>
                  {data.checks.length} checks cover provenance, dates,
                  duplicates, metadata, translations and fixture separation.
                </p>
                <p>
                  {data.warnings.length} source lifecycle notices are explicitly
                  retained in the Source Ledger.
                </p>
              </>
            )}
          </Status>
          <Link className="text-link" to="/sources">
            Inspect the Source Ledger
            <ArrowRight size={15} />
          </Link>
        </aside>
      </div>
    </>
  );
}
