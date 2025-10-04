
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import re
from tempfile import NamedTemporaryFile
from pathlib import Path

# -------------------------------
# Pydantic models
# -------------------------------
class Span(BaseModel):
    text: str
    start: int
    end: int
    match_type: Literal["dictionary", "abbrev", "ner"] = "dictionary"
    concept_id: Optional[str] = None
    semantic_type: Optional[str] = None
    confidence: Optional[float] = 0.95
    expanded: Optional[str] = None  # for abbreviations

class ExtractRequest(BaseModel):
    text: str

class ExtractResponse(BaseModel):
    original_text: str
    spans: List[Span]

# -------------------------------
# Minimal term dictionary (seed it; extend later)
# term -> (concept_id, semantic_type)
# -------------------------------
TERM_DICT = {
    "hypertension": ("MESH:D006973", "DiseaseOrSyndrome"),
    "htn": ("MESH:D006973", "DiseaseOrSyndrome"),
    "dm2": ("MESH:D003924", "DiseaseOrSyndrome"),
    "diabetes mellitus": ("MESH:D003920", "DiseaseOrSyndrome"),
    "sob": ("SYMPTOM:SOB", "Finding"),
    "shortness of breath": ("SYMPTOM:SOB", "Finding"),
    "troponin": ("LAB:TROP", "LaboratoryProcedure"),
    "pneumonia": ("MESH:D011014", "DiseaseOrSyndrome"),
    "pe": ("MESH:D011655", "DiseaseOrSyndrome"),  # beware collisions: 'pe' can be 'pulmonary embolism' or 'physical education'
    "pulmonary embolism": ("MESH:D011655", "DiseaseOrSyndrome"),
    "hx": (None, "Modifier"),
    "c/o": (None, "Modifier"),
    "r/o": (None, "Modifier"),
    "wnl": (None, "Modifier"),
}

# Common abbreviations expanded when possible (document-local mapping is better; this is a seed)
ABBREV_EXPANSIONS = {
    "htn": "hypertension",
    "dm2": "type 2 diabetes",
    "sob": "shortness of breath",
    "hx": "history",
    "c/o": "complains of / reports",
    "r/o": "rule out",
    "wnl": "within normal limits",
    "pe": "pulmonary embolism",
}

# -------------------------------
# Helpers
# -------------------------------

def normalize(text: str) -> str:
    # basic normalization; keep punctuation that matters
    text = re.sub(r"\r\n?|\n", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_dict_spans(text: str) -> List[Span]:
    spans: List[Span] = []
    lowered = text.lower()
    # sort longer terms first to favor longer matches during overlap filtering
    for term in sorted(TERM_DICT.keys(), key=len, reverse=True):
        cid, stype = TERM_DICT[term]
        # allow word boundary around term; handle slashes and hyphens in simple way
        pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
        for m in re.finditer(pattern, lowered, flags=re.IGNORECASE):
            spans.append(Span(
                text=text[m.start():m.end()],
                start=m.start(),
                end=m.end(),
                match_type="dictionary",
                concept_id=cid,
                semantic_type=stype,
                confidence=0.97 if cid else 0.9,
                expanded=ABBREV_EXPANSIONS.get(term)
            ))
    # resolve overlaps: keep the longest span, then left-to-right
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    non_overlap: List[Span] = []
    last_end = -1
    for s in spans:
        if s.start >= last_end:
            non_overlap.append(s)
            last_end = s.end
        else:
            # overlapping: keep the longer one (already sorted by length desc for same start)
            # If overlap but starts later than previous, decide by length
            prev = non_overlap[-1]
            if (s.end - s.start) > (prev.end - prev.start):
                non_overlap[-1] = s
                last_end = s.end
    return non_overlap


def extract_text_from_upload(tmp_path: Path) -> str:
    suf = tmp_path.suffix.lower()
    if suf in (".txt", ".md", ".csv"):
        return tmp_path.read_text(encoding="utf-8", errors="ignore")
    if suf == ".docx":
        try:
            import docx
        except Exception:
            raise HTTPException(status_code=400, detail=".docx support not installed; remove python-docx or install it")
        d = docx.Document(str(tmp_path))
        return "\n".join(p.text for p in d.paragraphs)
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {suf}. Use .txt or .docx for this MVP.")

# -------------------------------
# FastAPI app
# -------------------------------
app = FastAPI(title="Medical Jargon Extractor — MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/v1/extract_terms", response_model=ExtractResponse)
async def extract_terms(req: ExtractRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    text = normalize(req.text)
    spans = find_dict_spans(text)
    return ExtractResponse(original_text=text, spans=spans)

@app.post("/v1/extract_terms_upload", response_model=ExtractResponse)
async def extract_terms_upload(file: UploadFile = File(...)):
    with NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        raw = extract_text_from_upload(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
    text = normalize(raw)
    spans = find_dict_spans(text)
    return ExtractResponse(original_text=text, spans=spans)
