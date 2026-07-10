"""
build_eval_holdout.py
=====================
PRISM | Layer 2 | Module 1 — Real-World Holdout Set Builder

Steps:
  1. Load PhishingEmailDataset (Ling.csv + Nigerian_Fraud.csv) and
     reconstruct the exact text field used in prepare_text_dataset.py.
  2. Hash every row and match against training CSV hashes.
  3. Print the EXPLICIT list of rows already used in training.
  4. From the REMAINING (never-used) rows, sample ~25-30 phishing rows.
  5. From Sentences_AllAgree.txt's unused rows, sample ~25-30 legit rows.
  6. Run TF-IDF cosine check (threshold 0.85) against BOTH:
       - original 8,680-row CSV
       - deduped 7,814-row CSV
     Flag any near-match as REVIEW.
  7. Save data/eval/real_world_eval.csv with schema:
       text, label, source_type, source_file, source_row_idx,
       confidence_flag
  8. Print full overlap report.

Usage:
  python scripts/build_eval_holdout.py

Author : PRISM ML Team
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
MODULE1_DIR   = SCRIPT_DIR.parent
DATA_DIR      = MODULE1_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVAL_DIR      = DATA_DIR / "eval"

LING_CSV      = RAW_DIR / "PhishingEmailDataset" / "Ling.csv"
FRAUD_CSV     = RAW_DIR / "PhishingEmailDataset" / "Nigerian_Fraud.csv"
FINBANK_TXT   = RAW_DIR / "FinancialPhraseBank-v1.0" / "Sentences_AllAgree.txt"

TRAIN_CSV_ORIG   = PROCESSED_DIR / "finbert_text_training_data.csv"
TRAIN_CSV_DEDUPED = PROCESSED_DIR / "finbert_text_training_data_deduped.csv"
OUTPUT_CSV    = EVAL_DIR / "real_world_eval.csv"

NEAR_DUP_THRESHOLD = 0.85
SAMPLE_N           = 28   # target per class (gives 56 total, within 50-60 range)
SEED               = 42

# ---------------------------------------------------------------------------
# Logging — force UTF-8 on Windows
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
log = logging.getLogger("build_eval_holdout")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _md5(text: str) -> str:
    return hashlib.md5(_norm(text).encode("utf-8")).hexdigest()


def _near_dup_flags(
    candidate_texts: list[str],
    reference_texts: list[str],
    threshold: float = NEAR_DUP_THRESHOLD,
    label: str = "ref",
) -> list[str]:
    """
    For each candidate text, return "REVIEW" if cosine sim >= threshold
    against any reference text, else "OK".
    """
    log.info("  TF-IDF near-dup check: %d candidates vs %d references (%s) ...",
             len(candidate_texts), len(reference_texts), label)

    all_texts = candidate_texts + reference_texts
    vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
        dtype=np.float32,
    )
    X = vec.fit_transform(all_texts)
    n_cand = len(candidate_texts)
    X_cand = X[:n_cand]
    X_ref  = X[n_cand:]

    # cosine_similarity returns shape (n_cand, n_ref)
    sims = cosine_similarity(X_cand, X_ref)
    flags = []
    for i, row in enumerate(sims):
        max_sim = float(row.max())
        if max_sim >= threshold:
            log.warning(
                "  NEAR-DUP REVIEW candidate[%d] max_sim=%.4f | text[:80]: %s",
                i, max_sim, candidate_texts[i][:80],
            )
            flags.append("REVIEW")
        else:
            flags.append("OK")

    review_count = flags.count("REVIEW")
    log.info("  Near-dup check (%s): %d REVIEW, %d OK", label, review_count, len(flags) - review_count)
    return flags


# ---------------------------------------------------------------------------
# Step 1: Load training data for matching
# ---------------------------------------------------------------------------

def load_training_hashes() -> tuple[set[str], set[str], list[str], list[str]]:
    """
    Returns (orig_hashes, deduped_hashes, orig_texts, deduped_texts).
    """
    log.info("Loading original training CSV: %s", TRAIN_CSV_ORIG)
    df_orig = pd.read_csv(TRAIN_CSV_ORIG)
    orig_texts  = df_orig["text"].astype(str).tolist()
    orig_hashes = set(df_orig["text"].apply(_md5))
    log.info("  Original training rows: %d", len(df_orig))

    log.info("Loading deduped training CSV: %s", TRAIN_CSV_DEDUPED)
    df_ded = pd.read_csv(TRAIN_CSV_DEDUPED)
    deduped_texts  = df_ded["text"].astype(str).tolist()
    deduped_hashes = set(df_ded["text"].apply(_md5))
    log.info("  Deduped training rows: %d", len(df_ded))

    return orig_hashes, deduped_hashes, orig_texts, deduped_texts


# ---------------------------------------------------------------------------
# Step 2: Load and match PhishingEmailDataset
# ---------------------------------------------------------------------------

def load_phishing_dataset(
    orig_hashes: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads Ling.csv + Nigerian_Fraud.csv, reconstructs text field,
    matches against training hashes.

    Returns:
      phish_all   — all raw phishing rows with hash + used_in_training flag
      phish_used  — rows already in training (for explicit report)
      phish_avail — never-seen rows available for holdout
    """
    log.info("=" * 60)
    log.info("STEP 2 — Loading PhishingEmailDataset")

    frames = []

    # --- Ling.csv ---
    log.info("  Loading Ling.csv ...")
    try:
        df_ling = pd.read_csv(
            LING_CSV,
            usecols=["subject", "body", "label"],
            dtype={"label": int},
            on_bad_lines="skip",
            low_memory=False,
            encoding="utf-8",
            encoding_errors="replace",
        )
    except TypeError:
        df_ling = pd.read_csv(
            LING_CSV,
            usecols=["subject", "body", "label"],
            dtype={"label": int},
            on_bad_lines="skip",
            low_memory=False,
        )
    df_ling["subject"] = df_ling["subject"].fillna("").astype(str)
    df_ling["body"]    = df_ling["body"].fillna("").astype(str)
    df_ling["text"]    = (df_ling["subject"] + " " + df_ling["body"]).str.strip()
    df_ling["source_file"] = "Ling.csv"
    df_ling["source_row_idx"] = df_ling.index
    log.info("  Ling.csv loaded: %d rows, label dist: %s",
             len(df_ling), df_ling["label"].value_counts().to_dict())
    frames.append(df_ling[["text", "label", "source_file", "source_row_idx"]])

    # --- Nigerian_Fraud.csv (all label=1) ---
    log.info("  Loading Nigerian_Fraud.csv ...")
    try:
        df_fraud = pd.read_csv(
            FRAUD_CSV,
            usecols=["subject", "body"],
            on_bad_lines="skip",
            low_memory=False,
            encoding="utf-8",
            encoding_errors="replace",
        )
    except Exception:
        df_fraud = pd.read_csv(
            FRAUD_CSV,
            usecols=["subject", "body"],
            on_bad_lines="skip",
            low_memory=False,
        )
    df_fraud["subject"] = df_fraud["subject"].fillna("").astype(str)
    df_fraud["body"]    = df_fraud["body"].fillna("").astype(str)
    df_fraud["text"]    = (df_fraud["subject"] + " " + df_fraud["body"]).str.strip()
    df_fraud["label"]   = 1
    df_fraud["source_file"] = "Nigerian_Fraud.csv"
    df_fraud["source_row_idx"] = df_fraud.index
    log.info("  Nigerian_Fraud.csv loaded: %d rows", len(df_fraud))
    frames.append(df_fraud[["text", "label", "source_file", "source_row_idx"]])

    phish_all = pd.concat(frames, ignore_index=True)
    phish_all = phish_all[phish_all["text"].str.len() >= 20].copy()
    phish_all["hash"] = phish_all["text"].apply(_md5)

    # --- Match against training ---
    phish_all["used_in_training"] = phish_all["hash"].isin(orig_hashes)
    phish_used  = phish_all[phish_all["used_in_training"]].copy()
    phish_avail = phish_all[~phish_all["used_in_training"]].copy()

    log.info("  Total PhishingEmailDataset rows (after len filter): %d", len(phish_all))
    log.info("  Rows ALREADY in training (exact hash match)       : %d", len(phish_used))
    log.info("  Rows NEVER SEEN (available for holdout)           : %d", len(phish_avail))

    # Print explicit list of used rows
    log.info("=" * 60)
    log.info("EXPLICIT LIST — PhishingEmailDataset rows in training CSV:")
    log.info("  (source_file | source_row_idx | label | text[:60])")
    for _, row in phish_used.iterrows():
        log.info("  %s | row %d | label=%d | %s",
                 row["source_file"], row["source_row_idx"],
                 row["label"], row["text"][:60])
    log.info("  Total: %d rows already used.", len(phish_used))

    return phish_all, phish_used, phish_avail


# ---------------------------------------------------------------------------
# Step 3: Load unused FinancialPhraseBank rows
# ---------------------------------------------------------------------------

def load_finbank_unused(orig_hashes: set[str]) -> pd.DataFrame:
    log.info("=" * 60)
    log.info("STEP 3 — Loading FinancialPhraseBank (Sentences_AllAgree.txt)")

    rows = []
    with open(FINBANK_TXT, encoding="utf-8", errors="replace") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line or "@" not in line:
                continue
            text, _sentiment = line.rsplit("@", 1)
            text = text.strip()
            if text:
                rows.append({"text": text, "label": 0,
                             "source_file": "Sentences_AllAgree.txt",
                             "source_row_idx": idx})

    df = pd.DataFrame(rows)
    df["hash"] = df["text"].apply(_md5)
    df["used_in_training"] = df["hash"].isin(orig_hashes)

    used   = df[df["used_in_training"]]
    unused = df[~df["used_in_training"]]
    log.info("  Total AllAgree rows   : %d", len(df))
    log.info("  Used in training      : %d", len(used))
    log.info("  Available for holdout : %d", len(unused))

    return unused


# ---------------------------------------------------------------------------
# Step 4 & 5: Sample holdout rows
# ---------------------------------------------------------------------------

def sample_holdout(
    phish_avail: pd.DataFrame,
    finbank_unused: pd.DataFrame,
    n: int = SAMPLE_N,
    seed: int = SEED,
) -> pd.DataFrame:
    log.info("=" * 60)
    log.info("STEP 4/5 — Sampling holdout rows (n=%d per class)", n)

    # --- Phishing side: prefer label=1 (genuine threats), then supplement ---
    phish_threat = phish_avail[phish_avail["label"] == 1]
    if len(phish_threat) < n:
        log.warning("  Only %d threat rows available, sampling all.", len(phish_threat))
        phish_sample = phish_threat.copy()
    else:
        phish_sample = phish_threat.sample(n=n, random_state=seed)
    phish_sample = phish_sample.copy()
    phish_sample["source_type"] = "real_world_holdout"
    log.info("  Phishing sample rows : %d (from %d available threat rows)",
             len(phish_sample), len(phish_threat))

    # --- Legit side: unused AllAgree rows ---
    if len(finbank_unused) < n:
        log.warning("  Only %d legit rows available, sampling all.", len(finbank_unused))
        legit_sample = finbank_unused.copy()
    else:
        legit_sample = finbank_unused.sample(n=n, random_state=seed)
    legit_sample = legit_sample.copy()
    legit_sample["source_type"] = "real_world_holdout"
    log.info("  Legit sample rows    : %d (from %d available legit rows)",
             len(legit_sample), len(finbank_unused))

    combined = pd.concat([phish_sample, legit_sample], ignore_index=True)
    combined = combined.sample(frac=1, random_state=seed).reset_index(drop=True)
    log.info("  Combined holdout rows: %d", len(combined))
    return combined


# ---------------------------------------------------------------------------
# Step 6: TF-IDF near-dup check
# ---------------------------------------------------------------------------

def run_near_dup_verification(
    holdout: pd.DataFrame,
    orig_texts: list[str],
    deduped_texts: list[str],
) -> pd.DataFrame:
    log.info("=" * 60)
    log.info("STEP 6 — TF-IDF near-dup verification (threshold=%.2f)", NEAR_DUP_THRESHOLD)

    cands = holdout["text"].astype(str).tolist()

    # Against original training set
    flags_orig = _near_dup_flags(cands, orig_texts, label="original-8680")

    # Against deduped training set
    flags_ded  = _near_dup_flags(cands, deduped_texts, label="deduped-7814")

    # Combined flag: REVIEW if flagged by either
    combined_flags = [
        "REVIEW" if (fo == "REVIEW" or fd == "REVIEW") else "OK"
        for fo, fd in zip(flags_orig, flags_ded)
    ]

    holdout = holdout.copy()
    holdout["confidence_flag"] = combined_flags

    review_rows = holdout[holdout["confidence_flag"] == "REVIEW"]
    log.info("  Rows flagged REVIEW (near-dup to training): %d", len(review_rows))
    if len(review_rows) > 0:
        for _, row in review_rows.iterrows():
            log.warning("  REVIEW | label=%d | source=%s | text[:80]: %s",
                        row["label"], row["source_file"], row["text"][:80])

    return holdout


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("PRISM | Module 1 | Real-World Holdout Builder")
    log.info("=" * 60)

    # 1. Load training hashes
    orig_hashes, deduped_hashes, orig_texts, deduped_texts = load_training_hashes()

    # 2. PhishingEmailDataset matching
    phish_all, phish_used, phish_avail = load_phishing_dataset(orig_hashes)

    # 3. FinancialPhraseBank unused rows
    finbank_unused = load_finbank_unused(orig_hashes)

    # 4/5. Sample holdout
    holdout = sample_holdout(phish_avail, finbank_unused)

    # 6. Near-dup verification against BOTH training sets
    holdout = run_near_dup_verification(holdout, orig_texts, deduped_texts)

    # 7. Final schema: text, label, source_type, source_file, source_row_idx, confidence_flag
    holdout_final = holdout[[
        "text", "label", "source_type",
        "source_file", "source_row_idx", "confidence_flag"
    ]].copy()

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    holdout_final.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    log.info("=" * 60)
    log.info("Saved holdout CSV -> %s  (%d rows)", OUTPUT_CSV, len(holdout_final))
    log.info("Label dist  : %s", holdout_final["label"].value_counts().to_dict())
    log.info("Confidence  : %s", holdout_final["confidence_flag"].value_counts().to_dict())
    log.info("Source dist : %s", holdout_final["source_file"].value_counts().to_dict())
    log.info("=" * 60)

    # 8. Summary overlap report
    print("\n" + "=" * 60)
    print("OVERLAP REPORT — PhishingEmailDataset vs Training CSV")
    print("=" * 60)
    print(f"Total PhishingEmailDataset rows loaded   : {len(phish_all):,}")
    print(f"Already in training (exact hash match)   : {len(phish_used):,}")
    print(f"Available for holdout                    : {len(phish_avail):,}")
    print(f"  - Ling.csv used in training            : {len(phish_used[phish_used['source_file']=='Ling.csv']):,}")
    print(f"  - Nigerian_Fraud.csv used in training  : {len(phish_used[phish_used['source_file']=='Nigerian_Fraud.csv']):,}")
    print()
    print(f"FinancialPhraseBank AllAgree rows        : {len(finbank_unused) + (len(holdout[holdout['label']==0]) if 'label' in holdout else 0):,}")
    print(f"  Already in training                    : (see audit report)")
    print(f"  Available                              : {len(finbank_unused):,}")
    print()
    print(f"Holdout set final                        : {len(holdout_final):,} rows")
    print(f"  Label=1 (phishing/threat)              : {int((holdout_final['label']==1).sum())}")
    print(f"  Label=0 (legit)                        : {int((holdout_final['label']==0).sum())}")
    print(f"  REVIEW flags (near-dup to training)    : {int((holdout_final['confidence_flag']=='REVIEW').sum())}")
    print("=" * 60)


if __name__ == "__main__":
    main()
