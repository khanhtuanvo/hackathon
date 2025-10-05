import time
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple, List, Literal
import re, html 
import httpx

HIGHLIGHT_RE = re.compile(r'<span class="qt\d+">(.*?)</span>', re.I | re.S)
P_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)

# ---------------------------
# Endpoints & code systems
# ---------------------------
MPLUS_WS = "https://wsearch.nlm.nih.gov/ws/query"           # Web Service (keyword search)
MPLUS_CONNECT = "https://connect.medlineplus.gov/service"   # Connect (code → topic)

# Code system OIDs for Connect
CODE_SYSTEMS: Dict[str, str] = {
    "SNOMEDCT": "2.16.840.1.113883.6.96",
    "ICD10CM": "2.16.840.1.113883.6.90",
    "RXCUI": "2.16.840.1.113883.6.88",
    "LOINC": "2.16.840.1.113883.6.1",
}

Lang = Literal["en", "es"]

# Simple in-memory cache (term/code → response) to reduce calls during one process lifetime
_CACHE: Dict[Tuple[str, str, str], Tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours


def _cache_get(key: Tuple[str, str, str]) -> Optional[dict]:
    now = time.time()
    item = _CACHE.get(key)
    if not item:
        return None
    ts, payload = item
    if now - ts > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: Tuple[str, str, str], payload: dict) -> None:
    _CACHE[key] = (time.time(), payload)


# ---------------------------
# Web Service (keyword search)
# ---------------------------
async def medlineplus_search(terms: list[str], lang: Lang = "en") -> Optional[list[dict]]:
    result = []
    for term in terms:
        db = "healthTopicsSpanish" if lang == "es" else "healthTopics"
        cache_key = ("ws", lang, term.strip().lower())
        cached = _cache_get(cache_key)
        if cached:
            result.append(cached)
            continue

        params = {"db": db, "term": term}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(MPLUS_WS, params=params)
                r.raise_for_status()
        except Exception:
            result.append(None)
            continue

        try:
            root = ET.fromstring(r.text)
            doc = root.find(".//list/document")
            if doc is None:
                result.append(None)
                continue

            title_raw = doc.findtext("./content[@name='title']") or ""
            url       = (doc.findtext("./content[@name='url']") or "").strip()

            # FullSummary can appear as 'FullSummary' (capital F,S) or 'full-summary'
            full_raw  = (doc.findtext("./content[@name='FullSummary']") or
                        doc.findtext("./content[@name='full-summary']") or "")
            snippet_raw = doc.findtext("./content[@name='snippet']") or ""

            # Prefer the first <p> of FullSummary; fall back to cleaned snippet
            first_p = first_paragraph_from_fullsummary(full_raw)
            summary = first_p if first_p else clean_medlineplus_text(snippet_raw)

            title = clean_medlineplus_text(title_raw)
            searchResult = {"title": title, "url": url, "summary": summary, "source": "MedlinePlus Web Service"}
            _cache_set(cache_key, searchResult)
            result.append(searchResult)
        except Exception:
            result.append(None)
    return result



# ---------------------------
# High-level helper
# ---------------------------
async def explain_span(span_text: str, lang: Lang = "en",
                       code: Optional[str] = None,
                       code_system: Optional[str] = None) -> Optional[dict]:
    """
    Try Connect (if code provided) then fallback to WS search.
    Returns dict: {title, url, summary, source} or None.
    """
    # Prefer Connect when a code is provided
    if code and code_system:
        via_code = await medlineplus_connect(code_system=code_system, code=code, lang=lang)
        if via_code:
            return via_code

    # Fallback to keyword search (use a normalized/expanded term ideally)
    via_term = await medlineplus_search(span_text, lang=lang)
    return via_term


async def enrich_spans_with_medlineplus(
    spans: List[dict],       # list of your Span-like dicts
    lang: Lang = "en"
) -> List[dict]:
    """
    For each span, attach a 'medlineplus' field with {title, url, summary, source} when found.
    Tries code-based lookup first if span contains 'concept_id' you can map to a code system.
    """
    out = []
    for s in spans:
        term = s.get("expanded") or s.get("text") or ""
        code = None
        code_system = None

        # Example mapping: if your concept_id encodes the system (e.g., "RXCUI:12345")
        cid = s.get("concept_id")
        if cid and ":" in cid:
            prefix, code_val = cid.split(":", 1)
            # Normalize common prefixes to our CODE_SYSTEMS
            prefix_upper = prefix.upper()
            if prefix_upper in ("SNOMED", "SNOMEDCT"):
                code_system = "SNOMEDCT"; code = code_val
            elif prefix_upper in ("ICD10", "ICD10CM"):
                code_system = "ICD10CM"; code = code_val
            elif prefix_upper in ("RXCUI", "RXNORM"):
                code_system = "RXCUI"; code = code_val
            elif prefix_upper == "LOINC":
                code_system = "LOINC"; code = code_val

        expl = await explain_span(term, lang=lang, code=code, code_system=code_system)
        s = dict(s)  # copy
        if expl:
            s["medlineplus"] = expl
        out.append(s)
    return out

def clean_medlineplus_text(raw: str) -> str:
    if not raw:
        return ""
    s = HIGHLIGHT_RE.sub(r"\1", raw)          # remove highlight spans
    s = re.sub(r"<[^>]+>", "", s)             # strip remaining HTML
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
def first_paragraph_from_fullsummary(raw_html: str) -> str | None:
    """Return cleaned text of the FIRST <p> in FullSummary; None if not found."""
    if not raw_html:
        return None
    m = P_RE.search(raw_html)
    if not m:
        return None
    return clean_medlineplus_text(m.group(1))

def trim_to_complete_sentences(text: str) -> str:
    """Drop a trailing fragment (e.g., ‘When you have …’) in a snippet."""
    if not text:
        return text
    parts = SENT_END.split(text)
    if len(parts) < 3:
        return text
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sentences.append((parts[i] + parts[i+1]).strip())
    # If original ends with punctuation, keep all; else drop last partial
    if text.rstrip().endswith(('.', '!', '?')):
        return " ".join(sentences)
    return " ".join(sentences[:-1]).strip() or text