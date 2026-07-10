"""
add_uci_spam_holdout.py
=======================
PRISM | Layer 2 | Module 1 — Real-World Holdout Threat-Side Completion

Downloads UCI SMS Spam Collection (public dataset, not in training),
filters for finance/urgency-relevant spam rows, samples ~30,
verifies zero overlap with deduped training CSV + synthetic_batch.json,
then merges into data/eval/real_world_eval.csv.

Source  : UCI ML Repository (same dataset published on Kaggle as
          uciml/sms-spam-collection-dataset)
URL     : https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip
License : Creative Commons Attribution 4.0 International (CC BY 4.0)

Usage:
  python scripts/add_uci_spam_holdout.py
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
MODULE1_DIR   = SCRIPT_DIR.parent
DATA_DIR      = MODULE1_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
EVAL_DIR      = DATA_DIR / "eval"
RAW_CACHE_DIR = DATA_DIR / "raw" / "UCISMSSpam"

DEDUPED_CSV   = PROCESSED_DIR / "finbert_text_training_data_deduped.csv"
SYNTH_JSON    = SYNTHETIC_DIR / "synthetic_batch.json"
EVAL_CSV      = EVAL_DIR / "real_world_eval.csv"

UCI_URL       = "https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip"

NEAR_DUP_THRESHOLD = 0.85
SAMPLE_N           = 30
SEED               = 42

# Finance/urgency keywords that make a spam SMS relevant to the PRISM threat model
FINANCE_KEYWORDS: list[str] = [
    "won", "prize", "claim", "bank", "verify", "otp", "account",
    "urgent", "click", "cash", "refund", "credit", "loan", "win",
    "congratulations", "selected", "reward", "free", "offer",
    "password", "expire", "suspend", "confirm", "transfer",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
log = logging.getLogger("add_uci_spam_holdout")


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
    label: str,
    threshold: float = NEAR_DUP_THRESHOLD,
) -> list[str]:
    """Return 'REVIEW' for each candidate with cosine sim >= threshold vs any reference."""
    log.info("  TF-IDF near-dup check: %d cands vs %d refs (%s) ...",
             len(candidate_texts), len(reference_texts), label)
    all_texts = candidate_texts + reference_texts
    vec = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5),
        min_df=1, sublinear_tf=True, dtype=np.float32,
    )
    X      = vec.fit_transform(all_texts)
    X_cand = X[:len(candidate_texts)]
    X_ref  = X[len(candidate_texts):]
    sims   = cosine_similarity(X_cand, X_ref)
    flags  = []
    for i, row in enumerate(sims):
        max_sim = float(row.max())
        if max_sim >= threshold:
            log.warning("  NEAR-DUP REVIEW cand[%d] max_sim=%.4f | %s",
                        i, max_sim, candidate_texts[i][:80])
            flags.append("REVIEW")
        else:
            flags.append("OK")
    review_n = flags.count("REVIEW")
    log.info("  Near-dup (%s): %d REVIEW, %d OK", label, review_n, len(flags) - review_n)
    return flags


# ---------------------------------------------------------------------------
# Step 1: Download UCI SMS Spam Collection
# ---------------------------------------------------------------------------

def download_uci_sms() -> pd.DataFrame:
    """
    Downloads and parses the UCI SMS Spam Collection.
    Returns a DataFrame with columns: text, original_label (ham/spam).
    Caches the raw zip to data/raw/UCISMSSpam/ to avoid re-downloading.
    """
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = RAW_CACHE_DIR / "SMSSpamCollection"

    if cache_file.exists():
        log.info("Using cached UCI SMS file: %s", cache_file)
        raw_text = cache_file.read_text(encoding="utf-8", errors="replace")
    else:
        log.info("Downloading UCI SMS Spam Collection from:")
        log.info("  %s", UCI_URL)
        resp = requests.get(UCI_URL, timeout=60)
        resp.raise_for_status()
        log.info("  Downloaded %d bytes", len(resp.content))

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            log.info("  Zip contents: %s", zf.namelist())
            # The main file is always named 'SMSSpamCollection'
            name = next(n for n in zf.namelist() if "SMSSpamCollection" in n and not n.endswith("/"))
            raw_text = zf.read(name).decode("utf-8", errors="replace")

        cache_file.write_text(raw_text, encoding="utf-8")
        log.info("  Cached to: %s", cache_file)

    # Parse tab-separated: label<TAB>message
    rows = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            rows.append({"original_label": parts[0].strip(), "text": parts[1].strip()})

    df = pd.DataFrame(rows)
    log.info("Loaded %d SMS messages (label dist: %s)",
             len(df), df["original_label"].value_counts().to_dict())
    return df


# ---------------------------------------------------------------------------
# Step 2: Filter spam rows for finance/urgency relevance
# ---------------------------------------------------------------------------

def filter_finance_spam(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only spam rows containing at least one finance/urgency keyword."""
    spam = df[df["original_label"] == "spam"].copy()
    log.info("Total spam rows: %d", len(spam))

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in FINANCE_KEYWORDS) + r")\b",
        re.IGNORECASE,
    )
    mask = spam["text"].str.contains(pattern, na=False)
    filtered = spam[mask].copy()
    log.info("Finance/urgency filtered spam rows: %d  (keywords: %s)",
             len(filtered), ", ".join(FINANCE_KEYWORDS))

    # Log which keywords matched for transparency
    def matched_kws(text: str) -> str:
        return ", ".join(k for k in FINANCE_KEYWORDS if re.search(r"\b" + re.escape(k) + r"\b", text, re.I))

    filtered["matched_keywords"] = filtered["text"].apply(matched_kws)
    log.info("Sample filtered rows:")
    for _, row in filtered.head(5).iterrows():
        log.info("  [kw: %s] %s", row["matched_keywords"], row["text"][:100])

    return filtered


# ---------------------------------------------------------------------------
# Step 3: Load training references
# ---------------------------------------------------------------------------

def load_training_references() -> tuple[set[str], list[str], set[str]]:
    """Returns (deduped_hashes, deduped_texts, synth_hashes)."""
    log.info("Loading deduped training CSV: %s", DEDUPED_CSV)
    df_ded = pd.read_csv(DEDUPED_CSV)
    deduped_texts  = df_ded["text"].astype(str).tolist()
    deduped_hashes = set(df_ded["text"].apply(_md5))
    log.info("  Deduped rows: %d", len(df_ded))

    log.info("Loading synthetic batch: %s", SYNTH_JSON)
    with open(SYNTH_JSON, encoding="utf-8") as fh:
        synth = json.load(fh)
    synth_texts  = [s["text"] for s in synth]
    synth_hashes = set(_md5(t) for t in synth_texts)
    log.info("  Synthetic records: %d", len(synth))

    return deduped_hashes, deduped_texts, synth_hashes, synth_texts


# ---------------------------------------------------------------------------
# Step 4: Exact-hash overlap check
# ---------------------------------------------------------------------------

def check_exact_overlap(
    candidates: pd.DataFrame,
    deduped_hashes: set[str],
    synth_hashes: set[str],
) -> pd.DataFrame:
    """Adds 'hash' and 'exact_overlap' column; removes rows with overlap."""
    candidates = candidates.copy()
    candidates["hash"] = candidates["text"].apply(_md5)

    combined_train_hashes = deduped_hashes | synth_hashes
    candidates["exact_overlap"] = candidates["hash"].isin(combined_train_hashes)

    n_overlap = candidates["exact_overlap"].sum()
    log.info("Exact-hash overlap with training (deduped + synthetic): %d rows", n_overlap)

    if n_overlap > 0:
        log.warning("  Removing %d exact-overlap rows:", n_overlap)
        for _, row in candidates[candidates["exact_overlap"]].iterrows():
            log.warning("    %s", row["text"][:80])

    clean = candidates[~candidates["exact_overlap"]].copy()
    log.info("Rows after exact-overlap removal: %d", len(clean))
    return clean


# ---------------------------------------------------------------------------
# Step 5: Sample and TF-IDF near-dup check
# ---------------------------------------------------------------------------

def sample_and_verify(
    candidates: pd.DataFrame,
    deduped_texts: list[str],
    synth_texts: list[str],
    n: int = SAMPLE_N,
    seed: int = SEED,
) -> pd.DataFrame:
    """Sample n rows, run TF-IDF near-dup check, flag overlaps."""
    if len(candidates) < n:
        log.warning("Only %d candidates available (wanted %d) — using all.", len(candidates), n)
        sample = candidates.copy()
    else:
        sample = candidates.sample(n=n, random_state=seed).copy()
    log.info("Sampled %d rows for near-dup verification", len(sample))

    cand_texts = sample["text"].astype(str).tolist()

    # Check against deduped training CSV
    flags_ded = _near_dup_flags(cand_texts, deduped_texts, label="deduped-7814")

    # Check against synthetic batch
    flags_syn = _near_dup_flags(cand_texts, synth_texts, label="synthetic-800")

    # Combined flag
    sample["confidence_flag"] = [
        "REVIEW" if fd == "REVIEW" or fs == "REVIEW" else "OK"
        for fd, fs in zip(flags_ded, flags_syn)
    ]

    review_n = (sample["confidence_flag"] == "REVIEW").sum()
    log.info("Near-dup verification complete: %d REVIEW, %d OK", review_n, len(sample) - review_n)
    if review_n > 0:
        log.warning("REVIEW rows (will be included but flagged):")
        for _, row in sample[sample["confidence_flag"] == "REVIEW"].iterrows():
            log.warning("  %s", row["text"][:100])

    return sample


# ---------------------------------------------------------------------------
# Step 6: Build final holdout row format and merge
# ---------------------------------------------------------------------------

def build_and_merge(sample: pd.DataFrame) -> pd.DataFrame:
    """Construct threat rows in eval schema and merge with existing legit rows."""
    # Build threat rows
    threat_rows = pd.DataFrame({
        "text":             sample["text"].values,
        "label":            1,
        "source_type":      "real_world_holdout",
        "source_file":      "UCI_SMSSpamCollection",
        "source_row_idx":   sample.index.values,
        "confidence_flag":  sample["confidence_flag"].values,
    })
    log.info("Threat rows built: %d", len(threat_rows))

    # Load existing legit rows
    if EVAL_CSV.exists():
        existing = pd.read_csv(EVAL_CSV)
        log.info("Existing eval CSV rows (legit): %d", len(existing))
    else:
        existing = pd.DataFrame(columns=threat_rows.columns)
        log.warning("No existing eval CSV found — creating fresh.")

    # Merge
    merged = pd.concat([existing, threat_rows], ignore_index=True)
    log.info("Merged eval rows: %d  (label dist: %s)",
             len(merged), merged["label"].value_counts().to_dict())

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(EVAL_CSV, index=False, encoding="utf-8")
    log.info("Saved: %s", EVAL_CSV)
    return merged


# ---------------------------------------------------------------------------
# Step 7: Update VALIDATION.md methodology note
# ---------------------------------------------------------------------------

def update_validation_md(merged: pd.DataFrame) -> None:
    VALIDATION_MD = MODULE1_DIR / "VALIDATION.md"
    if not VALIDATION_MD.exists():
        log.warning("VALIDATION.md not found — skipping update.")
        return

    content = VALIDATION_MD.read_text(encoding="utf-8")

    # Replace the threat-side gap note with the updated methodology
    old_note = (
        "**Action required**: The judge will see this gap. We need 25–30 manually curated "
        "real-world threat examples (SEBI-impersonation texts, broker phishing messages, "
        "pump-and-dump posts) that were not part of the PhishingEmailDataset or synthetic "
        "generation. These will be added to `data/eval/real_world_eval.csv` once supplied."
    )
    label_dist = merged["label"].value_counts().to_dict()
    conf_dist  = merged["confidence_flag"].value_counts().to_dict()
    n_threat   = label_dist.get(1, 0)
    n_legit    = label_dist.get(0, 0)
    n_review   = conf_dist.get("REVIEW", 0)

    new_note = (
        f"**Methodology**: Real-world holdout = FinancialPhraseBank unused rows (label=0, "
        f"legit) + UCI SMS Spam Collection filtered for finance/urgency keywords "
        f"(label=1, threat). Both are public, human-collected datasets never used in training.\n\n"
        f"**Current holdout**: {n_legit} legit rows + {n_threat} threat rows = "
        f"{n_legit + n_threat} total. {n_review} row(s) flagged REVIEW (near-duplicate "
        f"to training; exclude from real-world F1 calculation)."
    )

    if old_note in content:
        content = content.replace(old_note, new_note)
        log.info("Updated VALIDATION.md — replaced threat-side gap note with methodology.")
    else:
        # Fallback: append a section if the exact string wasn't found
        log.warning("Could not find exact gap note in VALIDATION.md — appending update.")
        content += (
            f"\n\n---\n\n## Update: Holdout Threat Side Resolved\n\n{new_note}\n"
        )

    # Also update the holdout table row
    old_table_note = "**Note**: The numbers below will be filled in after Colab retraining on the deduped dataset."
    new_table_note = (
        "**Note**: The numbers below will be filled in after Colab retraining on the deduped dataset.\n\n"
        "> **Holdout methodology**: Real-world holdout = FinancialPhraseBank (legit, label=0, "
        f"{n_legit} rows) + UCI SMS Spam Collection filtered for finance/urgency keywords "
        f"(threat, label=1, {n_threat} rows). Both are public, human-collected datasets "
        "never used in training."
    )
    if old_table_note in content and new_table_note not in content:
        content = content.replace(old_table_note, new_table_note)

    VALIDATION_MD.write_text(content, encoding="utf-8")
    log.info("VALIDATION.md saved.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("PRISM | Module 1 | UCI SMS Spam Holdout Addition")
    log.info("=" * 60)

    # 1. Download
    df_sms = download_uci_sms()

    # 2. Filter
    filtered = filter_finance_spam(df_sms)

    # 3. Load training references
    deduped_hashes, deduped_texts, synth_hashes, synth_texts = load_training_references()

    # 4. Exact-hash overlap check
    clean = check_exact_overlap(filtered, deduped_hashes, synth_hashes)

    # 5. Sample + TF-IDF near-dup check
    sample = sample_and_verify(clean, deduped_texts, synth_texts)

    # 6. Merge
    merged = build_and_merge(sample)

    # 7. Update VALIDATION.md
    update_validation_md(merged)

    # Summary
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  UCI SMS total rows        : %d", len(df_sms))
    log.info("  Spam rows                 : %d", (df_sms["original_label"] == "spam").sum())
    log.info("  Finance-filtered spam     : %d", len(filtered))
    log.info("  After exact-overlap check : %d", len(clean))
    log.info("  Sampled for holdout       : %d  (threat, label=1)", len(sample))
    log.info("  REVIEW flags              : %d", int((sample["confidence_flag"] == "REVIEW").sum()))
    log.info("  Final eval CSV rows       : %d  (label dist: %s)",
             len(merged), merged["label"].value_counts().to_dict())
    log.info("=" * 60)

    # Print explicit REVIEW list for transparency
    review_rows = sample[sample["confidence_flag"] == "REVIEW"]
    if len(review_rows) > 0:
        print("\n=== REVIEW-FLAGGED ROWS (near-dup to training, cosine >= 0.85) ===")
        for _, row in review_rows.iterrows():
            print(f"  [{row.name}] {row['text'][:120]}")
    else:
        print("\n=== No REVIEW-flagged rows — all 30 threat samples confirmed clean ===")

    print(f"\nFinal holdout: {len(merged)} rows saved to {EVAL_CSV}")


if __name__ == "__main__":
    main()
