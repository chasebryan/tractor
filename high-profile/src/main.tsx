import {
  Activity,
  BookOpen,
  Check,
  ChevronRight,
  FolderOpen,
  Globe2,
  Layers3,
  Menu,
  Search,
  ShieldCheck,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useSearchParams,
} from "react-router-dom";

import { Empty } from "./components";
import { Context } from "./context";
import { EvidenceInspector } from "./inspector";
import {
  Directory,
  Home,
  Investigation,
  Investigations,
  Methodology,
  Profile,
  SearchPage,
  SourceDetail,
  Sources,
  Watch,
} from "./pages";
import "./styles.css";
function Shell() {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const [mobile, setMobile] = useState(false),
    [toast, setToast] = useState("");
  const claimId = params.get("claim");
  useEffect(() => {
    setMobile(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement) &&
        !document.querySelector("dialog[open]")
      ) {
        e.preventDefault();
        (
          document.querySelector(
            'input[aria-label="Search public evidence"]',
          ) as HTMLInputElement
        )?.focus();
      }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, []);
  const nav = [
    ["/", "Index", Search],
    ["/directory?kind=COUNTRY", "Countries", Globe2],
    ["/directory", "Entities", Layers3],
    ["/sources", "Source Ledger", BookOpen],
    ["/watch", "Watch", Activity],
    ["/investigations", "Investigations", FolderOpen],
  ] as const;
  return (
    <Context.Provider
      value={{
        inspect: (id, version) =>
          setParams((old) => {
            old.set("claim", id);
            version
              ? old.set("version", String(version))
              : old.delete("version");
            return old;
          }),
        notify: setToast,
      }}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside
        id="workspace-navigation"
        className={`sidebar ${mobile ? "open" : ""}`}
      >
        <Link to="/" className="brand">
          <span className="brand-symbol">
            H<span />
          </span>
          <div>
            HIGH-PROFILE<small>PUBLIC EVIDENCE. IN CONTEXT.</small>
          </div>
        </Link>
        <div className="nav-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map(([url, title, Icon]) => (
            <NavLink
              key={title}
              to={url}
              end={url === "/" || url === "/directory"}
              className={({ isActive }) =>
                (
                  url.includes("?")
                    ? location.pathname === "/directory" &&
                      params.get("kind") === "COUNTRY"
                    : url === "/directory"
                      ? location.pathname === "/directory" &&
                        params.get("kind") !== "COUNTRY"
                      : isActive
                )
                  ? "active"
                  : ""
              }
            >
              <Icon size={18} />
              <span>{title}</span>
              {title === "Index" && <span className="nav-shortcut">/</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">THE RESEARCH PRINCIPLE</span>
          <p>
            Every claim has evidence.
            <br />
            Every change has a history.
          </p>
          <div className="side-rule" />
        </div>
        <div className="sidebar-bottom">
          <Link to="/methodology">
            <ShieldCheck size={17} />
            Methodology & integrity
          </Link>
          <span className="sidebar-release">
            INDEX 1.0 <span>PUBLIC SOURCES</span>
          </span>
        </div>
      </aside>
      {mobile && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="app-main">
        <header className="topbar">
          <button
            className="mobile-toggle"
            aria-label="Open navigation"
            aria-expanded={mobile}
            aria-controls="workspace-navigation"
            onClick={() => setMobile(!mobile)}
          >
            <Menu size={21} />
          </button>
          <div className="topbar-path">
            WORKSPACE <ChevronRight size={12} />
            <span>
              {location.pathname === "/"
                ? "OVERVIEW"
                : location.pathname.split("/")[1].toUpperCase()}
            </span>
          </div>
          <div className="topbar-status">
            <span className="status-square" />
            DEVELOPMENT COLLECTION <span className="topbar-divider" />{" "}
            <span>OPEN SOURCES</span>
            <Globe2 size={15} />
          </div>
        </header>
        <main id="main" className="page">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/directory" element={<Directory />} />
            <Route path="/profiles/:id" element={<Profile />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/sources/:id" element={<SourceDetail />} />
            <Route path="/watch" element={<Watch />} />
            <Route path="/investigations" element={<Investigations />} />
            <Route path="/investigations/:id" element={<Investigation />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route
              path="*"
              element={
                <Empty
                  title="Page not found"
                  text="Use the research navigation to return to the index."
                />
              }
            />
          </Routes>
        </main>
        <footer>
          <span>
            HIGH-PROFILE <span className="footer-dash">/</span> Global Nuclear
            Capabilities Intelligence
          </span>
          <span>EVIDENCE, NOT CERTAINTY.</span>
        </footer>
      </div>
      {claimId && (
        <EvidenceInspector
          key={`${claimId}:${params.get("version") ?? ""}`}
          claimId={claimId}
          initialVersion={params.get("version") ?? undefined}
          onClose={() =>
            setParams((old) => {
              old.delete("claim");
              old.delete("version");
              return old;
            })
          }
        />
      )}
      <div className={`toast ${toast ? "visible" : ""}`} role="status">
        {toast && (
          <>
            <Check size={17} />
            {toast}
          </>
        )}
      </div>
    </Context.Provider>
  );
}
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="empty">
        <h1>HIGH-PROFILE</h1>
        <p>The workspace could not render. Reload to try again.</p>
        <button className="button" onClick={() => location.reload()}>
          Reload workspace
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>,
);
