import re
import joblib
import numpy as np
from typing import List, Tuple

# 1) Load your trained model
pipe = joblib.load("jargon_detector_lr.joblib")  # change path if needed

# 2) Candidate generator: 1–3 word n-grams (keeps hyphenated words)
WORD = re.compile(r"\w+(?:[-’']\w+)*", flags=re.UNICODE)

def generate_candidates(text: str, max_len: int = 3) -> List[Tuple[str, int, int]]:
    tokens = [(m.group(0), m.start(), m.end()) for m in WORD.finditer(text)]
    cands = []
    for i in range(len(tokens)):
        for L in range(1, max_len + 1):
            j = i + L
            if j <= len(tokens):
                start = tokens[i][1]
                end   = tokens[j-1][2]
                phrase = text[start:end]
                cands.append((phrase, start, end))
    # Deduplicate by (lowercased phrase, span)
    seen = set()
    uniq = []
    for phrase, s, e in cands:
        key = (phrase.lower(), s, e)
        if key not in seen:
            seen.add(key)
            uniq.append((phrase, s, e))
    return uniq

# 3) Score candidates and filter by threshold
def score_candidates(cands: List[Tuple[str,int,int]], threshold: float = 0.5):
    phrases = [p for p,_,_ in cands]
    probs = pipe.predict_proba(phrases)[:, 1]
    hits = [(p, s, e, float(pr)) for (p, s, e), pr in zip(cands, probs) if pr >= threshold]
    # sort by probability (desc), then span start
    hits.sort(key=lambda x: (-x[3], x[1]))
    return hits

# 4) Optional: longest-match filtering so overlapping hits don’t double-mark
def longest_non_overlapping(hits):
    hits_sorted = sorted(hits, key=lambda x: (x[1], -(x[2]-x[1])))  # by start, then longer first
    kept = []
    last_end = -1
    for p, s, e, pr in hits_sorted:
        if s >= last_end:    # non-overlap
            kept.append((p, s, e, pr))
            last_end = e
    # resort by prob for display
    kept.sort(key=lambda x: -x[3])
    return kept

# 5) Annotate paragraph (plain text)
def annotate_paragraph(text: str, hits: List[Tuple[str,int,int,float]]) -> str:
    # Insert tags from the end to keep indices stable
    spans = sorted(hits, key=lambda x: x[1], reverse=True)
    out = text
    for phrase, s, e, pr in spans:
        # Add a compact marker; you can store pr if you like
        tag_open = f"[JARGON] "
        tag_close = f" [/JARGON]"
        out = out[:s] + tag_open + out[s:e] + tag_close + out[e:]
    return out


# cands = generate_candidates(input, max_len=5)
# hits = score_candidates(cands, threshold=0.5)
# hits = longest_non_overlapping(hits)

# print("Top detections (term, start, end, prob):")
# for term, s, e, pr in hits[:20]:
#     print(f"{term:45s}  [{s}:{e}]  p={pr:.3f}")

# annotated = annotate_paragraph(paragraph, hits)
# print("\nAnnotated paragraph:\n")
# print(annotated)
