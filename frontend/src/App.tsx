import { useMemo, useState } from "react";
import { extractText, extractUpload } from "./api";

interface Span {
  text: string;
  start: number;
  end: number;
  match_type: string;
  concept_id?: string;
  semantic_type?: string;
  confidence?: number;
  expanded?: string;
}

export default function App() {
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [spans, setSpans] = useState<Span[]>([]);
  const [info, setInfo] = useState<Span | null>(null);

  async function onExplain() {
    try {
      setLoading(true); setError(null); setSpans([]); setInfo(null);
      const data = file ? await extractUpload(file) : await extractText(text);
      setText(data.original_text || text);
      setSpans(data.spans || []);
    } catch (e: any) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const highlighted = useMemo(() => renderHighlighted(text, spans, setInfo), [text, spans]);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16, fontFamily: "Inter, system-ui, Arial" }}>
      <h2>Medical Jargon Extractor — MVP</h2>
      <p style={{ color: "#555" }}>Paste text or upload a .txt/.docx, click <b>Extract</b>, and we’ll highlight medical terms. Click a highlight to see details.</p>

      <label style={{ display: "block", marginTop: 8 }}>Paste text</label>
      <textarea
        rows={8}
        value={text}
        onChange={(e) => { setText(e.target.value); setFile(null); }}
        placeholder="Pt c/o cp x2d. Hx of HTN. Troponin WNL. R/o PE. Denies SOB today."
        style={{ width: "100%", padding: 8, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas" }}
      />

      <div style={{ margin: "12px 0" }}>
        <input type="file" accept=".txt,.docx" onChange={e => setFile(e.target.files?.[0] || null)} />
      </div>

      <button onClick={onExplain} disabled={loading} style={{ padding: "8px 14px" }}>
        {loading ? "Extracting…" : "Extract"}
      </button>

      {error && <div style={{ color: "#b91c1c", marginTop: 12 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginTop: 16 }}>
        <div>
          <h3>Document</h3>
          <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, minHeight: 180 }}>
            {highlighted}
          </div>
        </div>
        <div>
          <h3>Details</h3>
          <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12, minHeight: 180 }}>
            {info ? (
              <div>
                <div><b>Term:</b> {info.text}</div>
                {info.expanded && <div><b>Expanded:</b> {info.expanded}</div>}
                {info.semantic_type && <div><b>Type:</b> {info.semantic_type}</div>}
                {info.concept_id && <div><b>Concept:</b> {info.concept_id}</div>}
                {typeof info.confidence === "number" && <div><b>Confidence:</b> {(info.confidence*100).toFixed(0)}%</div>}
                <div style={{ marginTop: 6, color: "#6b7280", fontSize: 12 }}>
                  start={info.start}, end={info.end}, source={info.match_type}
                </div>
              </div>
            ) : (
              <div style={{ color: "#6b7280" }}>Click a highlighted term to see details here.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function renderHighlighted(text: string, spans: Span[], onPick: (s: Span) => void) {
  if (!text) return <div />;
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  const sorted = [...spans].sort((a, b) => a.start - b.start);
  sorted.forEach((s, i) => {
    if (cursor < s.start) parts.push(<span key={`p${i}`}>{text.slice(cursor, s.start)}</span>);
    parts.push(
      <mark
        key={`m${i}`}
        style={{ background: "#fde68a", padding: "0 2px", borderRadius: 3, cursor: "pointer" }}
        onClick={() => onPick(s)}
        title={`${s.text}${s.expanded ? ` → ${s.expanded}` : ''}`}
      >
        {text.slice(s.start, s.end)}
      </mark>
    );
    cursor = s.end;
  });
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);
  return <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{parts}</div>;
}

// 1. Start backend (`uvicorn` on :8000), then start frontend (`vite` on :5173).
// 2. Paste: `Pt c/o cp x2d. Hx of HTN. Troponin WNL. R/o PE. Denies SOB today.`
// 3. Click **Extract** → you should see highlights for terms in the seed dictionary.
// 4. Click a highlight → details appear in the right pane.

// ---

// ## 5) Next steps (when you’re ready)

// * Expand **TERM_DICT** (or load from a JSON/CSV) and add an **acronym detector** using document-local mappings.
// * Plug in **scispaCy NER** to boost recall and a simple **overlap merger** (we already have a basic one).
// * Add a **/translate** endpoint calling your AI model and include `plain_definition` per span to show in the popup.
// * Support **PDF** via `pymupdf`/`pdfplumber` and basic OCR for scanned docs.
// * Replace inline styles with Tailwind/shadcn for a polished look.

// That’s it—this is a clean foundation you can run right now and iterate on. ✅
