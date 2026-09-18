import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  ExternalLink,
  FolderOpen,
  Scale,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, date, label, useApi } from "./api";

import { Badge, Status } from "./components";
import { useActions } from "./context";
function SaveClaim({ claim }: { claim: any }) {
  const { data, reload } = useApi("/api/investigations");
  const [inv, setInv] = useState(""),
    [note, setNote] = useState(""),
    [title, setTitle] = useState(""),
    [pending, setPending] = useState(false);
  const { notify } = useActions();
  return (
    <details className="save-claim">
      <summary>
        <FolderOpen size={16} /> Save to investigation <ChevronDown size={15} />
      </summary>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setPending(true);
          try {
            let key = inv;
            if (!key) {
              const created = await api("/api/investigations", {
                method: "POST",
                body: JSON.stringify({ title }),
              });
              key = created.id;
              setInv(key);
              reload();
            }
            await api(`/api/investigations/${key}/items`, {
              method: "POST",
              body: JSON.stringify({ version_id: claim.id, note }),
            });
            notify("Claim version saved to investigation.");
          } catch (e) {
            notify((e as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <label>
          Investigation
          <select value={inv} onChange={(e) => setInv(e.target.value)}>
            <option value="">Create a new investigation</option>
            {data?.items.map((i: any) => (
              <option value={i.id} key={i.id}>
                {i.title}
              </option>
            ))}
          </select>
        </label>
        {!inv && (
          <label>
            New investigation title
            <input
              required
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
        )}
        <label>
          Analyst note
          <textarea
            value={note}
            maxLength={8000}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add context for your research…"
          />
        </label>
        <button className="button dark" disabled={pending}>
          {pending ? "Saving…" : "Save this version"}
        </button>
      </form>
    </details>
  );
}
export function EvidenceInspector({
  claimId,
  initialVersion,
  onClose,
}: {
  claimId: string;
  initialVersion?: string;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState("evidence"),
    [version, setVersion] = useState(initialVersion ?? "");
  const [params] = useSearchParams();
  const cutoff = params.get("as_of");
  const { data, error } = useApi(
    `/api/claims/${claimId}?${new URLSearchParams({ ...(version ? { version } : {}), ...(cutoff ? { as_of: cutoff } : {}) })}`,
  );
  useEffect(() => {
    const el = dialog.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  useEffect(() => {
    setVersion(initialVersion ?? "");
    setTab("evidence");
  }, [claimId, initialVersion]);
  return (
    <dialog
      className="inspector"
      ref={dialog}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-labelledby="inspector-title"
      onClick={(e) => {
        if (
          e.target === dialog.current &&
          e.clientX < dialog.current.getBoundingClientRect().left
        )
          onClose();
      }}
    >
      <div className="inspector-top">
        <span>
          <BookOpen size={17} /> EVIDENCE INSPECTOR
        </span>
        <button
          onClick={onClose}
          aria-label="Close evidence inspector"
          autoFocus
        >
          <X size={21} />
        </button>
      </div>
      <Status data={data} error={error}>
        {data && (
          <>
            <div className="inspector-heading">
              <Link to={`/profiles/${data.entity_slug}`} onClick={onClose}>
                {data.entity_name}
                <ArrowUpRight size={14} />
              </Link>
              <h2 id="inspector-title">{data.statement}</h2>
              <div className="badge-line">
                <Badge value={data.classification} />
                <Badge value={`${data.confidence} CONFIDENCE`} />
                {data.is_synthetic && (
                  <span className="synthetic">SYNTHETIC TEST CASE</span>
                )}
              </div>
              <div className="claim-reference">
                CLAIM {data.claim_id.slice(0, 8).toUpperCase()}{" "}
                <span>VERSION {data.version}</span>
              </div>
            </div>
            <div className="inspector-clocks">
              <div>
                <span>Effective</span>
                <strong>{date(data.effective_from)}</strong>
              </div>
              <div>
                <span>Publicly available</span>
                <strong>{date(data.public_on)}</strong>
              </div>
              <div>
                <span>Ingested</span>
                <strong>{date(data.recorded_at)}</strong>
              </div>
            </div>
            <div className="section-tabs inspector-tabs">
              {["evidence", "confidence", "history"].map((t) => (
                <button
                  key={t}
                  className={tab === t ? "active" : ""}
                  onClick={() => setTab(t)}
                >
                  {label(t)}
                  {t === "evidence" && (
                    <span className="tab-count">{data.evidence.length}</span>
                  )}
                </button>
              ))}
            </div>
            <div className="inspector-body">
              {tab === "evidence" && (
                <>
                  <div className="support-summary">
                    <span>
                      <Check size={14} />
                      {data.evidence_count} supporting fragment
                      {data.evidence_count !== 1 ? "s" : ""}
                    </span>
                    <span>
                      {data.independent_groups} publisher group
                      {data.independent_groups !== 1 ? "s" : ""}
                    </span>
                  </div>
                  {data.contradictions.map((c: any) => (
                    <div className="contradiction-note" key={c.id}>
                      <strong>
                        <Scale size={17} />
                        Conflicting assessment · {c.status}
                      </strong>
                      <p>{c.explanation}</p>
                      <p>{c.other_statement}</p>
                    </div>
                  ))}
                  {data.evidence.map((e: any) => (
                    <article
                      className={`evidence-card ${e.role === "CONTRADICTS" ? "contrary" : ""}`}
                      key={e.id}
                    >
                      <div className="evidence-card-label">
                        <span>
                          {e.role === "SUPPORTS"
                            ? "SUPPORTING EVIDENCE"
                            : e.role === "CONTRADICTS"
                              ? "CONTRADICTORY EVIDENCE"
                              : "CONTEXT"}
                        </span>
                        <span>TIER {e.tier}</span>
                      </div>
                      <h3>{e.publisher}</h3>
                      <Link
                        className="document-link"
                        to={`/sources/${e.source_id}`}
                        onClick={onClose}
                      >
                        {e.title}
                        <ArrowUpRight size={13} />
                      </Link>
                      <div className="quote-label">
                        {e.is_paraphrase
                          ? "EDITORIAL PARAPHRASE · NOT ORIGINAL TEXT"
                          : `ORIGINAL EXCERPT · ${e.language.toUpperCase()}`}
                      </div>
                      <blockquote lang={e.language}>
                        {e.original_text}
                      </blockquote>
                      {e.translations.map((t: any) => (
                        <div className="translation" key={t.id}>
                          <div className="quote-label">
                            TRANSLATION · {t.language.toUpperCase()}
                          </div>
                          <p>{t.translated_text}</p>
                          <small>
                            {t.engine} ·{" "}
                            {t.reviewed
                              ? "reviewed"
                              : "not externally reviewed"}
                          </small>
                        </div>
                      ))}
                      <div className="evidence-metadata">
                        <span>Published {date(e.published_on)}</span>
                        <Badge value={e.health} />
                      </div>
                      <p className="location-reference">{e.location}</p>
                      <details className="provenance-details">
                        <summary>
                          Inspect provenance chain <ChevronDown size={14} />
                        </summary>
                        <dl>
                          <dt>Publisher</dt>
                          <dd>
                            {e.publisher} · Tier {e.tier}
                          </dd>
                          <dt>Independence</dt>
                          <dd>{e.independence_group}</dd>
                          <dt>Retrieved</dt>
                          <dd>
                            {date(e.retrieved_at)} · {e.method}
                          </dd>
                          <dt>Extraction</dt>
                          <dd>
                            {e.extraction_method} · {date(e.extracted_at)}
                          </dd>
                          <dt>Licensing</dt>
                          <dd>{e.license}</dd>
                          <dt>Retrieval record</dt>
                          <dd>{e.retrieval_note}</dd>
                          <dt>Hash scope</dt>
                          <dd>{e.hash_scope}</dd>
                          <dt>SHA-256</dt>
                          <dd className="hash">{e.content_hash}</dd>
                        </dl>
                      </details>
                      {!e.synthetic_source && (
                        <a
                          className="original-link"
                          href={e.canonical_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open original source
                          <ExternalLink size={14} />
                        </a>
                      )}
                    </article>
                  ))}
                </>
              )}
              {tab === "confidence" && (
                <>
                  <h3>
                    Why {label(data.confidence).toLowerCase()} confidence?
                  </h3>
                  <p className="muted-text">
                    An explicit editorial assessment. These factors are not
                    combined into a hidden numerical score.
                  </p>
                  {Object.entries(data.confidence_rationale).map(([k, v]) => (
                    <div className="confidence-factor" key={k}>
                      <h4>{label(k)}</h4>
                      <p>{String(v)}</p>
                    </div>
                  ))}
                  <div className="notice">{data.notes}</div>
                </>
              )}
              {tab === "history" && (
                <>
                  <p className="muted-text">
                    Published versions are immutable. Select a version to
                    inspect the evidence used at that time.
                  </p>
                  {data.versions.map((v: any) => (
                    <button
                      className={`version-card ${v.id === data.id ? "selected" : ""}`}
                      key={v.id}
                      onClick={() => setVersion(String(v.version))}
                    >
                      <div>
                        <strong>Version {v.version}</strong>
                        <span>
                          {v.id === data.id
                            ? "Viewing"
                            : v.version === data.versions[0].version
                              ? "Latest in view"
                              : "Superseded"}
                        </span>
                      </div>
                      <p>{v.statement}</p>
                      <small>
                        {date(v.public_on)} · {label(v.confidence)} confidence
                      </small>
                    </button>
                  ))}
                  <p className="small-note">
                    Last reviewed {date(data.reviewed_at)}. Earlier knowledge is
                    not rewritten by later evidence.
                  </p>
                </>
              )}
              <SaveClaim claim={data} />
            </div>
          </>
        )}
      </Status>
    </dialog>
  );
}
