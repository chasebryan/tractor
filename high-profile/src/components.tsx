import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Search,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { date, label } from "./api";

import { useActions } from "./context";
export function Badge({
  value,
  muted = false,
}: {
  value: string;
  muted?: boolean;
}) {
  return (
    <span
      className={`badge ${muted ? "muted" : /DISPUTED|LOW|STALE|SUPERSEDED|UNKNOWN/.test(value) ? "amber" : /RETRACTED/.test(value) ? "red" : /DOCUMENTED|HIGH|OFFICIALLY/.test(value) ? "blue" : "muted"}`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function Status({
  data,
  error,
  children,
}: {
  data: any;
  error: string;
  children: React.ReactNode;
}) {
  return error ? (
    <div className="empty error" role="alert">
      <AlertTriangle />
      <h2>Unable to load this record</h2>
      <p>{error}</p>
      <button className="button" onClick={() => location.reload()}>
        Try again
      </button>
    </div>
  ) : data ? (
    children
  ) : (
    <div className="loading" role="status">
      <span className="loading-line" />
      Loading evidence…
    </div>
  );
}
export function Empty({
  title = "No matching evidence",
  text = "Try fewer filters or a broader search. This collection is deliberately limited.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="empty">
      <Search size={25} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function SearchBox({
  initial = "",
  large = false,
}: {
  initial?: string;
  large?: boolean;
}) {
  const [q, setQ] = useState(initial);
  const navigate = useNavigate();
  useEffect(() => setQ(initial), [initial]);
  return (
    <form
      className={`searchbox ${large ? "large" : ""}`}
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        navigate(`/search?q=${encodeURIComponent(q)}`);
      }}
    >
      <Search aria-hidden="true" size={large ? 24 : 20} />
      <input
        id={large ? "workspace-search" : undefined}
        aria-label="Search public evidence"
        placeholder="Search countries, programmes, systems, facilities, sources…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <kbd className="search-key">/</kbd>
      <button aria-label="Run search" type="submit">
        <ArrowRight size={22} />
      </button>
    </form>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function ClaimList({
  items,
  compact = false,
}: {
  items: any[];
  compact?: boolean;
}) {
  const { inspect } = useActions();
  if (!items.length) return <Empty />;
  return (
    <div className={`claim-list ${compact ? "compact" : ""}`}>
      <div className="claim-head">
        <span>SUBJECT / ASSESSMENT</span>
        <span>CLASSIFICATION</span>
        <span>CONFIDENCE</span>
        <span>EVIDENCE</span>
      </div>
      {items.map((c: any) => (
        <article className="claim-row" key={c.id}>
          <div className="claim-main">
            <div className="claim-kicker">
              <Link to={`/profiles/${c.entity_slug}`}>{c.entity_name}</Link>
              <span>·</span>
              <span>{date(c.public_on)}</span>
              {c.is_synthetic && <span className="synthetic">SYNTHETIC</span>}
            </div>
            <button
              className="claim-statement"
              onClick={() => inspect(c.claim_id)}
            >
              {c.statement}
              <ArrowUpRight size={15} />
            </button>
          </div>
          <div className="classification">
            <Badge value={c.classification} />
          </div>
          <div className="confidence">
            <span
              className={`confidence-mark ${c.confidence === "LOW" ? "low" : ""}`}
            />
            {label(c.confidence)}
          </div>
          <button className="evidence-link" onClick={() => inspect(c.claim_id)}>
            <BookOpen size={15} />
            {c.evidence_count} source{c.evidence_count !== 1 ? "s" : ""}
            {c.contrary_count > 0 && (
              <span className="dispute-dot" title="Contradictory evidence" />
            )}
            <ChevronRight size={15} />
          </button>
        </article>
      ))}
    </div>
  );
}
export function Timeline({ items }: { items: any[] }) {
  const { inspect } = useActions();
  return (
    <div className="timeline">
      {items.map((v: any) => (
        <article key={v.id}>
          <div className="timeline-date">
            <span>{date(v.public_on)}</span>
            <small>PUBLICLY AVAILABLE</small>
          </div>
          <div className="timeline-body">
            <div className="claim-kicker">
              VERSION {v.version} <Badge value={v.classification} />
            </div>
            <button
              className="claim-statement"
              onClick={() => inspect(v.claim_id, v.version)}
            >
              {v.statement}
            </button>
            <div className="timeline-clocks">
              <span>Effective {date(v.effective_from)}</span>
              <span>Ingested {date(v.recorded_at)}</span>
              <span>Confidence: {label(v.confidence)}</span>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
