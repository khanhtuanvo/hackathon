
import re
import joblib
import numpy as np

PIPE_PATH = "jargon_detector_lr.joblib"   # change if needed

pipe = joblib.load(PIPE_PATH)

# word tokens with optional internal hyphens/apostrophes
WORD = re.compile(r"\w+(?:[-’']\w+)*", flags=re.UNICODE)

# stopwords to ignore/trim at edges (lowercase)
STOPWORDS = {"a","an","and", "or", "of","how","where","when","whose","which","-","+","=","the","what","whom","has","have","upon", ",",";",".","if",":","was", "with", "were","i.e","is","are","am","not","this","that","these","those","in","on","at","as","but","can"}

def detect_jargon_terms(text: str, threshold: float = 0.5, max_ngram: int = 3, dedupe: bool = True) -> list[str]:
    """
    Return a list of predicted-jargon terms (all lowercase) from `text`.
    Rules:
      - Convert input to lowercase before everything else.
      - Skip single-word stopwords: and/or/of/was/with
      - For multi-word candidates, trim leading/trailing stopwords (keep internal ones).
      - Keep terms with P(jargon) >= threshold.
    """
    if not isinstance(text, str):
        return []
    text = text.lower()  # <---- force lowercase

    # 1) Tokenize to (token, start, end) on the *lowercased* text
    toks = [(m.group(0), m.start(), m.end()) for m in WORD.finditer(text)]

    def is_stop(tok: str) -> bool:
        return tok in STOPWORDS

    # 2) Build/trim candidates (1..max_ngram words)
    cands = []
    for i in range(len(toks)):
        for L in range(1, max_ngram + 1):
            j = i + L
            if j > len(toks):
                break

            # Trim stopwords at the edges
            start_idx, end_idx = i, j - 1
            while start_idx <= end_idx and is_stop(toks[start_idx][0]):
                start_idx += 1
            while end_idx >= start_idx and is_stop(toks[end_idx][0]):
                end_idx -= 1
            if start_idx > end_idx:
                continue

            s, e = toks[start_idx][1], toks[end_idx][2]
            phrase = text[s:e].strip()
            if not phrase or (start_idx == end_idx and is_stop(phrase)):
                continue
            cands.append((phrase, s, e))

    if not cands:
        return []

    # 3) Score candidates -> P(jargon)
    phrases = [p for p, _, _ in cands]
    if hasattr(pipe, "predict_proba"):
        # assumes positive class is index 1; if not, map via pipe.named_steps['clf'].classes_
        probs = pipe.predict_proba(phrases)[:, 1]
    else:
        # fallback for models without predict_proba
        dec = pipe.decision_function(phrases)
        if np.ndim(dec) > 1:
            dec = dec[:, 1]
        probs = 1 / (1 + np.exp(-dec))

    # 4) Keep only jargon
    jargon = [p for (p, _, _), pr in zip(cands, probs) if pr >= threshold]

    # 5) Optional dedupe (case-insensitive; everything is already lowercase)
    if dedupe:
        seen, out = set(), []
        for term in jargon:
            if term and term not in seen:
                seen.add(term)
                out.append(term)
        return out
    else:
        return [t for t in jargon if t]
    
text = "What do we mean by a cell type? This question has generated much tedious discussion, but the ultimate goal is simple – to find a way to single out a group of neurons that carry out a distinct task. In real life, we rarely know a cell's function at the first encounter, and the strategic path is to first identify cell types and then find out what they do. This kind of search is based on the fundamental premise that different structure indicates different function, ‘structure’ broadly defined here to include both morphology and the expression of functionally important proteins. This has proved over the years to be a reliable rule (a doubtful reader is invited to search for a counterexample)."
print(detect_jargon_terms(text, threshold=0.45))

