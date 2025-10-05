# add at the top
import os 
import shutil
# --- NEW: OpenAI and environment variable setup ---
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastapi.concurrency import run_in_threadpool # Keep for sync functions


from .services.medlineplus import (
    medlineplus_search,
)
from .services.jargon_detection import (
    detect_medical_jargon
)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import re
from tempfile import NamedTemporaryFile
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Initialize the Async OpenAI client
# It automatically reads the OPENAI_API_KEY from your .env file
client = AsyncOpenAI()


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
# With this simpler version:
class ExplainTermInContextRequest(BaseModel):
    term: str
    context_text: str

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



# -------------------------------
# FastAPI app
# -------------------------------
app = FastAPI(title="Medical Jargon Extractor — MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

# @app.post("/v1/extract_terms_upload", response_model=ExtractResponse)
# async def extract_terms_upload(file: UploadFile = File(...)):
#     orig_suffix = (Path(file.filename or "").suffix or "").lower()
#     with NamedTemporaryFile(delete=False, suffix=orig_suffix) as tmp:
#         file.file.seek(0)
#         shutil.copyfileobj(file.file, tmp)
#         tmp_path = Path(tmp.name)
#     try:
#         raw = extract_text_from_upload(
#             tmp_path,
#             original_filename=file.filename,
#             content_type=file.content_type,
#         )
#     finally:
#         try:
#             tmp_path.unlink()
#         except Exception:
#             pass

#     text = normalize(raw)
#     raw_spans = [s.model_dump() for s in find_dict_spans(text)]
#     # if you don’t want auto MedlinePlus enrichment, skip it:
#     # enriched = await enrich_spans_with_medlineplus(raw_spans, lang="en")
#     # typed_spans = [Span(**s) for s in enriched]
#     typed_spans = [Span(**s) for s in raw_spans]
#     return ExtractResponse(original_text=text, spans=typed_spans)


async def mp_search(terms: list[str] = Query(...), lang: str = "en") -> list[str]:
    """Keyword -> MedlinePlus Health Topic"""
    hits = await medlineplus_search(terms, lang="es" if lang == "es" else "en")

    description = []
    for term, hit in zip(terms, hits):
        final_prompt = f"""
        You are a helpful medical educator. Your task is to explain the following medical term in a simple and easy-to-understand way for someone with no health knowledge.
        Use the provided context text to understand how the term is being used.

        - Term to Explain: "{term}"
        - Full Context: "{hit}"

        Please provide a brief, simple explanation of the term. Use a relatable analogy if it helps.
        Focus only on explaining the term itself.
        """

        try:
            # 2. Call the OpenAI API asynchronously
            completion = await client.chat.completions.create(
                model="gpt-3.5-turbo", # Or "gpt-4o"
                messages=[
                    {"role": "user", "content": final_prompt}
                ]
            )
            simplified_text = completion.choices[0].message.content

            if not simplified_text:
                description.append("")
                raise HTTPException(status_code=500, detail="OpenAI returned an empty response.")

            description.append(simplified_text.strip())

        except Exception as e:
            # Handle potential API errors
            description.append("")
            raise HTTPException(status_code=500, detail=f"An error occurred with the OpenAI API: {e}")
    return description

@app.post("/execute")
async def execute(text: str):
    jargon_result = detect_medical_jargon(text)
    description = mp_search(jargon_result)
    return {
        "terms": jargon_result,
        "description": description
    }