import { useMemo, useState } from "react";
import { extractText, extractUpload, searchTerm} from "./api";
import "./App.css"; // <— add this

interface Span {
  text: string;
  start: number;
  end: number;
  match_type: string;
  concept_id?: string;
  semantic_type?: string;
  confidence?: number;
  expanded?: string;
  medlineplus?: { title?: string; url?: string; summary?: string };
}

export default function App() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [info, setInfo] = useState<Span | null>(null);
  const [mp, setMp] = useState<{ title?: string; url?: string; summary?: string } | null>(null);
  const [mpLoading, setMpLoading] = useState(false);

  async function onExplain() {
    try {
      setLoading(true); setError(null); setSpans([]); setInfo(null);
      const data = file ? await extractUpload(file) : await extractText(text);
      setText(data.original_text || text);
      setSpans(data.spans || []);
    } catch (e: any) {
      setError(e.message || "Request failed");
    } finally { setLoading(false); }
  }

  const highlighted = useMemo(
    () => renderHighlighted(text, spans, async (s: Span) => {
      setInfo(s);
      setMp(null);
      setMpLoading(true);
      try {
        const term = (s.expanded || s.text || "").trim();
        if (term) {
          const resp = await searchTerm(term);
          setMp(resp.result || null);
        }
      } finally {
        setMpLoading(false);
      }
    }),
    [text, spans]
  );


  return (
    <div className="app">
      <div className="container">
        {/* Header */}
        <div className="header">
          <div className="brand">
            <div className="logo">MeD</div>
            <div>
              <div style={{ fontWeight: 800 }}>MeDicT</div>
              <div className="subtitle">Medical Dictionary</div>
            </div>
          </div>
          <a className="link" href="" target="_blank" rel="noreferrer">MeDicT</a>
        </div>

        {/* Grid */}
        <div className="grid">
          {/* Left column */}
          <div>
            <div className="card">
              <div className="card-title">Input</div>
              {/* <div className="tabs">
                <button className="tab active" disabled>Paste text</button>
              </div> */}

              <label style={{ display: "block", marginTop: 8 }}>Input field</label>
              <textarea
                rows={8}
                value={text}
                onChange={(e) => { setText(e.target.value); setFile(null); }}
                placeholder="Enter your text"
                className="textarea"
              />

              <div style={{ margin: "12px 0" }}>
                <input type="file" accept=".txt,.docx" onChange={e => setFile(e.target.files?.[0] || null)} />
                <div className="input-hint">Accepted: .txt, .docx</div>
                {/* {file && <div className="file-tag">Selected: {file.name}</div>} */}
              </div>

              <div className="btn-row">
                <button onClick={onExplain} disabled={loading} className="btn btn-primary">
                  {loading ? <>Extracting <span className="spinner" /></> : "Extract & Highlight"}
                </button>
                <button
                  onClick={() => { setText(""); setFile(null); setSpans([]); setInfo(null); setError(null); }}
                  disabled={loading}
                  className="btn btn-ghost"
                >
                  Clear
                </button>
              </div>

              {error && <div className="error">{error}</div>}
            </div>

            <div className="card">
              <div className="card-title">Output</div>
              <div className="docbox">
                {loading ? <SkeletonLines lines={6} /> : highlighted}
              </div>
            </div>
          </div>

          {/* Right column */}
          <div>
            <div className="card">
              <div className="card-title">Details</div>
              {!info ? (
                <div className="subtitle">Click a highlighted term to see details here.</div>
              ) : (
                <div>
                  <div className="term-row">
                    <span className="term">{info.text}</span>
                  </div>

                  <div className="meta">
                    {/* {!!info.semantic_type && <span><b>Type:</b> {info.semantic_type} &nbsp; </span>} */}
                    {/* {typeof info.confidence === "number" && <span><b>Confidence:</b> {(info.confidence * 100).toFixed(0)}%</span>} */}
                  </div>

                  <div style={{ marginTop: 12 }}>
                    {mpLoading ? (
                      <SkeletonLines lines={3} />
                    ) : mp ? (
                      <>
                        <div className="kv">
                          <span className="kv-label">Title:</span>
                          <span className="kv-value">{mp.title || "—"}</span>
                        </div>

                        {mp.summary && (
                          <div style={{ color: "var(--muted-2)" }}>{mp.summary}</div>
                        )}

                        {mp.url && (
                          <div style={{ marginTop: 6 }}>
                            <a className="link" href={mp.url} target="_blank" rel="noreferrer">
                              Learn more →
                            </a>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="subtitle">No explanation found for this term.</div>
                    )}
                  </div>

                </div>
              )}
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}

function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skel-line" />
      ))}
    </div>
  );
}

function renderHighlighted(
  text: string,
  spans: Span[],
  onPick: (s: Span) => void | Promise<void>   // allow async
) {
  if (!text) return <div />;
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  sorted.forEach((s, i) => {
    if (cursor < s.start) parts.push(<span key={`p${i}`}>{text.slice(cursor, s.start)}</span>);
    parts.push(
      <mark
        key={`m${i}`}
        className="jargon"
        onClick={() => onPick(s)}
        title={`${s.text}${s.expanded ? ` → ${s.expanded}` : ""}`}
      >
        {text.slice(s.start, s.end)}
      </mark>
    );
    cursor = s.end;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{parts}</div>;
}
