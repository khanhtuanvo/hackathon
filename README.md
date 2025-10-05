# MedJar – Medical Jargon Detector & Simplifier (WebExtension + ML)

Detect medical jargon while you read any article and get simple explanations—right on the page.

- **Model:** NLP pipeline with **TF-IDF + Linear SVM**
- **Targets:** Medical-domain terms (e.g., diseases, procedures, signs/symptoms, medications)
- **Extension:** Highlights jargon in webpages and shows tooltips/popovers with plain-language explanations
- **Backend (optional):** FastAPI endpoint for inference & definitions; or **fully offline** via exported model weights

---

## ✨ Features

- **On-page scanning:** Extracts article text from the DOM and tokenizes/splits into phrases.
- **Jargon detection:** SVM classifier trained on labeled biomedical spans.
- **Explain in plain English:** Uses rule-based templates + public-source glossaries (e.g., MedlinePlus/NHS/NCIt—configure attribution).
- **Two deployment modes:**
  - **Local/offline:** Load TF-IDF vocab + SVM weights in the extension for client-side inference.
  - **API mode:** Send text to a FastAPI server for prediction + definitions.
- **Privacy-first:** No data leaves the page in offline mode. Opt-in telemetry only.

---

## 🧱 Repo Structure

```
.
├─ extension/                  # Chrome/Edge extension (React/Plasmo or vanilla)
│  ├─ src/
│  │  ├─ content.tsx          # Scans page, highlights terms, popovers
│  │  ├─ ui/                  # Tooltip/Popup components
│  │  ├─ ml/
│  │  │  ├─ model.json        # Exported SVM weights (coef, intercept)
│  │  │  ├─ vocab.json        # TF-IDF vocabulary
│  │  │  └─ tfidf_stats.json  # idf, norms, etc.
│  │  ├─ utils/text.ts        # DOM extraction, sentence/phrase splitting
│  │  └─ utils/infer.ts       # TF-IDF + SVM inference (JS)
│  └─ manifest.json
│
├─ backend/
│  ├─ app.py                  # FastAPI (predict/define endpoints)
│  ├─ artifacts/
│  │  ├─ vectorizer.pkl
│  │  ├─ svm.pkl
│  │  └─ label_map.json
│  └─ requirements.txt
│
├─ model/
│  ├─ train.ipynb             # E2E training notebook
│  ├─ train.py                # Scripted training
│  ├─ export_js.py            # Export sklearn artifacts → JSON for extension
│  └─ data/                   # Your datasets (spans/tokens/labels)
│
└─ README.md
```

---

## 📦 Quick Start

### 1) Set up Python & train the model

```bash
# create env
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r backend/requirements.txt  # includes scikit-learn, fastapi, uvicorn, pandas, joblib

# train SVM (uses TF-IDF + LinearSVC)
python model/train.py   --train data/train.csv   --dev data/dev.csv   --out backend/artifacts
```

**What `train.py` does**
- cleans text, lowercases, strips punctuation/stopwords
- builds `TfidfVectorizer(ngram_range=(1,3), min_df=2, sublinear_tf=True)`
- fits **LinearSVC** (good margin classifier for sparse features)
- saves: `vectorizer.pkl`, `svm.pkl`, `label_map.json`

### 2) Export artifacts for the WebExtension (offline mode)

```bash
python model/export_js.py   --vec backend/artifacts/vectorizer.pkl   --svm backend/artifacts/svm.pkl   --labels backend/artifacts/label_map.json   --out extension/src/ml
```

This writes:
- `vocab.json` (term → index)
- `tfidf_stats.json` (idf, norms, options)
- `model.json` (SVM coef, intercept, classes)

> The extension runs TF-IDF and the linear decision function in JS for **zero-server** inference.

### 3) Run the extension in dev

If you use **Plasmo**:

```bash
cd extension
npm i
npm run dev          # builds and watches
# Load the generated build in Chrome: chrome://extensions (Developer mode → Load unpacked)
```

**Edge**: same as Chrome (edge://extensions).

---

## 🔍 How It Works

1. **DOM Extraction**
   - `content.tsx` finds main article nodes (heuristics: `<article>`, large `<div>` blocks).
   - Merges contiguous text nodes, preserves paragraph breaks.

2. **Tokenization & Candidate Phrases**
   - Lowercase, strip punctuation.
   - Generate unigrams/bigrams/trigrams (windowed).
   - Optional filters: stopwords (`and, or, of, was, with…`) are dropped **unless** part of a learned phrase.

3. **Vectorization (TF-IDF)**
   - Uses exported `vocab.json` + `tfidf_stats.json`.
   - Builds a sparse vector in JS mirroring scikit-learn’s preprocessing.

4. **Classification (Linear SVM)**
   - Applies `decision = X · coef.T + intercept`.
   - One-vs-rest or direct LinearSVC classes → select jargon label or `O` (non-jargon).
   - Thresholding: optional margin threshold to trade precision/recall.

5. **Explanation**
   - If API mode is enabled, the extension calls `/define?term=…` to fetch a short definition from configured sources.
   - Otherwise, local rules + bundled mini-glossary (JSON) generate simplified definitions.

6. **UI**
   - Highlight spans with a subtle underline.
   - Hover/click → tooltip with **“What it means”** (plain language), **“Also called”**, and **“Learn more”** (attribution link).

---

## 🧪 Datasets & Labels

Use any medically-labeled spans dataset you have permission to use. Recommended label focus:

- `BIOLOGICAL_STRUCTURE`, `DIAGNOSTIC_PROCEDURE`, `DISEASE_DISORDER`,
- `MEDICATION`, `SIGN_SYMPTOM`, `THERAPEUTIC_PROCEDURE`

In `train.py`, map your dataset’s labels to the above set via `label_map.json`. Everything else can map to `O` (non-jargon).

---

## 📈 Evaluation (suggested)

```bash
python model/train.py --eval_only   --train data/train.csv --dev data/dev.csv   --out backend/artifacts
```

Report:
- Precision / Recall / F1 per label
- Macro-F1 and Micro-F1
- Confusion matrix (optional)
- Threshold sweep (if you apply probability calibration via `LinearSVC` + Platt/CalibratedClassifierCV)

---

## 🧩 API Mode (optional)

**FastAPI** server for inference + definitions.

```bash
uvicorn backend.app:app --reload --port 8000
```

**Endpoints**
- `POST /predict` → `{ text: str }` ⇒ `[{ span, label, score }]`
- `GET /define?term=dyspnea` → `{ term, definition, source_url, attribution }`

**Extension config**
- `extension/src/config.ts`:
  ```ts
  export const INFERENCE_MODE: "offline" | "api" = "offline"
  export const API_BASE = "http://localhost:8000"
  ```

---

## 🧠 Why SVM?

- Linear SVMs work **extremely well** with high-dimensional sparse TF-IDF features.
- Fast to train, tiny to ship (just coef/intercept + vocab), easy to run on-device.
- Great baseline for hackathons; can upgrade later to a small transformer if needed.

---

## 🔐 Privacy

- **Offline mode:** No text leaves the page.
- **API mode:** Text is sent to your server for inference/definitions—document this for users.
- No PII is logged unless explicitly enabled.

---

## ⚙️ Configuration

- **Thresholds:** `extension/src/ml/thresholds.ts` (per-label or global margin cut-off)
- **Stopwords:** `extension/src/ml/stopwords.json` (e.g., `and, or, of, was, with`)
- **Glossary:** `extension/src/data/glossary.json` for offline definitions
- **Attribution:** Add source notes for external definitions (e.g., MedlinePlus/NHS)

---

## 🛠️ Development Scripts

```bash
# Python
black model backend
pytest -q

# Extension
npm run dev
npm run build
```

Packaging for store:
- **Chrome Web Store**: upload zipped `/build` (ensure correct `manifest.json`).
- **Edge Add-ons**: similar submission; test in Edge beforehand.

---

## 🚧 Roadmap

- [ ] Add probabilistic calibration + confidence bins in tooltips
- [ ] Contextual grouping of multi-word spans (merge overlapping hits)
- [ ] Caching definitions + inline citations
- [ ] On-device tiny transformer (Distil/ELI5-style simplifier) as optional module
- [ ] i18n (English ↔ Vietnamese)

---

## 🤝 Contributing

PRs welcome! Please:
1. Open an issue describing the change.
2. Include evaluation diffs (metrics) if you modify the model.
3. Keep extension bundle size minimal.

---

## 📜 License

MIT (model weights may require dataset-specific terms; verify before redistribution).

---

## 📝 Appendix: Minimal Inference (JS)

```ts
// utils/infer.ts (sketch)
import vocab from "../ml/vocab.json"
import stats from "../ml/tfidf_stats.json"
import model from "../ml/model.json"

export function predict(tokens: string[]): { phrase: string; label: string; score: number }[] {
  // 1) build tf vector
  const tf = new Map<number, number>()
  for (const t of tokens) {
    const idx = (vocab as any)[t]
    if (idx !== undefined) tf.set(idx, (tf.get(idx) ?? 0) + 1)
  }
  // 2) tf-idf
  const rows: number[] = []
  const vals: number[] = []
  for (const [i, f] of tf.entries()) {
    const idf = (stats.idf as number[])[i] ?? 0
    rows.push(i); vals.push(Math.log1p(f) * idf)
  }
  // 3) linear scores per class: X·W + b
  const out = []
  for (let c = 0; c < model.coef.length; c++) {
    let s = model.intercept[c]
    const w = model.coef[c] as number[]
    for (let k = 0; k < rows.length; k++) s += vals[k] * (w[rows[k]] || 0)
    out.push({ label: model.classes[c], score: s })
  }
  // choose top label + apply threshold elsewhere
  return out.sort((a, b) => b.score - a.score)
}
```
