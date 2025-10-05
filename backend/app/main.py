# add at the top
import shutil
from typing import Optional
from .services.medlineplus import (
    medlineplus_search,
    medlineplus_connect,
    explain_span,
    enrich_spans_with_medlineplus,
)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
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
    expanded: Optional[str] = None
    # NEW:
    medlineplus: Optional[dict] = None


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


def extract_text_from_upload(
    tmp_path: Path,
    original_filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    """
    Decide how to read the file using:
    1) the temp file's suffix,
    2) or the original filename's suffix,
    3) or (last resort) the MIME type.
    """
    suffix = (tmp_path.suffix or "").lower()

    if not suffix and original_filename:
        suffix = (Path(original_filename).suffix or "").lower()

    if not suffix and content_type:
        # minimal MIME mapping
        if content_type == "text/plain":
            suffix = ".txt"
        elif content_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            suffix = ".docx"

    if suffix in (".txt", ".md", ".csv"):
        return tmp_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".docx":
        try:
            import docx  # python-docx
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="python-docx not installed. Run: pip install python-docx",
            )
        d = docx.Document(str(tmp_path))
        return "\n".join(p.text for p in d.paragraphs)

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type: {suffix or '(unknown)'} . Use .txt or .docx for this MVP.",
    )

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
    raw_spans = [s.model_dump() for s in find_dict_spans(text)]  # pydantic v2: model_dump
    enriched = await enrich_spans_with_medlineplus(raw_spans, lang="en")
    # rebuild Span objects (keeps medlineplus field)
    typed_spans = [Span(**s) for s in enriched]
    return ExtractResponse(original_text=text, spans=typed_spans)

# @app.post("/v1/extract_terms_upload", response_model=ExtractResponse)
# async def extract_terms_upload(file: UploadFile = File(...)):
#     # ... your existing temp-file logic (with suffix fix) ...
#     text = normalize(raw)
#     raw_spans = [s.model_dump() for s in find_dict_spans(text)]
#     enriched = await enrich_spans_with_medlineplus(raw_spans, lang="en")
#     typed_spans = [Span(**s) for s in enriched]
#     return ExtractResponse(original_text=text, spans=typed_spans)

@app.post("/v1/extract_terms_upload", response_model=ExtractResponse)
async def extract_terms_upload(file: UploadFile = File(...)):
    orig_suffix = (Path(file.filename or "").suffix or "").lower()
    with NamedTemporaryFile(delete=False, suffix=orig_suffix) as tmp:
        file.file.seek(0)
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        raw = extract_text_from_upload(
            tmp_path,
            original_filename=file.filename,
            content_type=file.content_type,
        )
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

    text = normalize(raw)
    raw_spans = [s.model_dump() for s in find_dict_spans(text)]
    # if you don’t want auto MedlinePlus enrichment, skip it:
    # enriched = await enrich_spans_with_medlineplus(raw_spans, lang="en")
    # typed_spans = [Span(**s) for s in enriched]
    typed_spans = [Span(**s) for s in raw_spans]
    return ExtractResponse(original_text=text, spans=typed_spans)


@app.get("/v1/mp/search")
async def mp_search(term: str = Query(...), lang: str = "en"):
    """Keyword -> MedlinePlus Health Topic"""
    hit = await medlineplus_search(term, lang="es" if lang == "es" else "en")
    return {"term": term, "lang": lang, "result": hit}

@app.get("/v1/mp/connect")
async def mp_connect(code_system: str, code: str, lang: str = "en"):
    """Code (e.g., SNOMEDCT/ICD10CM/RXCUI/LOINC) -> MedlinePlus topic"""
    hit = await medlineplus_connect(code_system, code, lang="es" if lang == "es" else "en")
    return {"code_system": code_system, "code": code, "lang": lang, "result": hit}

@app.get("/v1/mp/explain")
async def mp_explain(term: str, code: Optional[str] = None,
                     code_system: Optional[str] = None, lang: str = "en"):
    """Try Connect (if code provided) then fallback to keyword search."""
    hit = await explain_span(term, lang="es" if lang == "es" else "en",
                             code=code, code_system=code_system)
    return {"term": term, "code": code, "code_system": code_system, "lang": lang, "result": hit}