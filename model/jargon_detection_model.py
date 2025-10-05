# Import library
import json
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report, roc_auc_score, average_precision_score,
    roc_curve, precision_recall_curve, confusion_matrix
)
import joblib
import numpy as np
import matplotlib.pyplot as plt   # <-- plotting

ALLOWED = {
    "BIOLOGICAL_STRUCTURE",
    "DIAGNOSTIC_PROCEDURE",
    "DISEASE_DISORDER",
    "MEDICATION",
    "SIGN_SYMPTOM",
    "THERAPEUTIC_PROCEDURE",

    }


def as_bool(x):
    return (x is True) or (str(x).strip().lower() in {"true","1","yes","y","t"})

full ="medical_jargon_dataset.json"

rows = json.load(open(full, "r", encoding="utf-8"))
df = pd.DataFrame(rows)

# Harmonize boolean key names
if "is_medical_jargon" not in df.columns:
    for c in df.columns:
        if c.lower().replace("_","") == "ismedicaljargon":
            df["is_medical_jargon"] = df[c]

df["is_medical_jargon"] = df["is_medical_jargon"].apply(as_bool)
if "label" not in df.columns:
    df["label"] = None

pos = df[(df["is_medical_jargon"] == True) & (df["label"].isin(ALLOWED))].copy()
neg = df[df["is_medical_jargon"] == False].copy()

# Downsample negatives to keep balance (optional)
if len(neg) > 2 * len(pos) and len(pos) > 0:
    neg = neg.sample(n=2*len(pos), random_state=42)

use = pd.concat([pos.assign(y=1), neg.assign(y=0)], ignore_index=True)
use = use.dropna(subset=["text"]).sample(frac=1.0, random_state=42).reset_index(drop=True)


X = use["text"].astype(str).values
y = use["y"].astype(int).values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

pipe = Pipeline([
    ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=3)), #abc
    ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear"))
])

pipe.fit(X_train, y_train)

proba = pipe.predict_proba(X_test)[:, 1]
pred = (proba >= 0.5).astype(int)

print(classification_report(y_test, pred, digits=3))
print("ROC-AUC:", roc_auc_score(y_test, proba))
print("AUPRC:", average_precision_score(y_test, proba))

joblib.dump(pipe,  "jargon_detector_lr.joblib")


