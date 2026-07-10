"""
audit_and_dedup.py
==================
PRISM | Layer 2 | Module 1 — Data Integrity Audit

Performs:
  1. Synthetic cross-reference  — verifies how synthetic_batch.json
     was merged into the training CSV.
  2. Exact-duplicate detection  — MD5 hash on normalised text.
  3. Near-duplicate detection   — TF-IDF cosine similarity (threshold 0.85).
  4. Split-straddling leakage   — reconstructs the *would-have-been*
     80/20 split (same seed used by train_finbert_baseline) and counts
     how many duplicate pairs straddle train/test.
  5. Deduplication              — keeps one representative per cluster.
  6. Fresh stratified 80/20 split on deduped data (seed=42).
  7. Saves  data/processed/finbert_text_training_data_deduped.csv
  8. Writes data/processed/dedup_report.md

Usage:
  python scripts/audit_and_dedup.py

Author : PRISM ML Team
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
MODULE1_DIR   = SCRIPT_DIR.parent
DATA_DIR      = MODULE1_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"

INPUT_CSV     = PROCESSED_DIR / "finbert_text_training_data.csv"
SYNTH_JSON    = SYNTHETIC_DIR / "synthetic_batch.json"
OUTPUT_CSV    = PROCESSED_DIR / "finbert_text_training_data_deduped.csv"
REPORT_MD     = PROCESSED_DIR / "dedup_report.md"

NEAR_DUP_THRESHOLD = 0.85
SPLIT_SEED         = 42
TEST_SIZE          = 0.20

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("audit_and_dedup")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Normalise text for hash comparison: strip, lowercase, collapse whitespace."""
    import re
    return re.sub(r"\s+", " ", text.strip().lower())


def _md5(text: str) -> str:
    return hashlib.md5(_norm(text).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Step 1: Load data
# ---------------------------------------------------------------------------

def load_data() -> tuple[pd.DataFrame, list[dict]]:
    log.info("Loading training CSV: %s", INPUT_CSV)
    df = pd.read_csv(INPUT_CSV)
    log.info("  → %d rows, columns: %s", len(df), df.columns.tolist())

    log.info("Loading synthetic batch: %s", SYNTH_JSON)
    with open(SYNTH_JSON, encoding="utf-8") as fh:
        synth = json.load(fh)
    log.info("  → %d synthetic records", len(synth))

    return df, synth


# ---------------------------------------------------------------------------
# Step 2: Synthetic cross-reference
# ---------------------------------------------------------------------------

def cross_reference_synthetic(df: pd.DataFrame, synth: list[dict]) -> dict:
    """
    Check how many synthetic rows appear verbatim in the CSV.
    Returns a dict with counts.
    """
    log.info("─" * 60)
    log.info("STEP 2 — Synthetic cross-reference")

    csv_hashes = set(df["text"].apply(_md5))

    synth_hashes = [_md5(s["text"]) for s in synth]
    found_in_csv = sum(1 for h in synth_hashes if h in csv_hashes)
    missing_from_csv = len(synth_hashes) - found_in_csv

    log.info("  Synthetic records in JSON       : %d", len(synth))
    log.info("  Found verbatim in training CSV  : %d", found_in_csv)
    log.info("  NOT in training CSV             : %d  (dropped during balancing)", missing_from_csv)

    # Count synthetic rows that ARE in the CSV by label
    synth_df = pd.DataFrame(synth)
    synth_df["hash"] = synth_df["text"].apply(_md5)
    synth_in_csv = synth_df[synth_df["hash"].isin(csv_hashes)]

    label_counts = synth_in_csv["label"].value_counts().to_dict()
    source_counts = synth_in_csv["source_type"].value_counts().to_dict()
    log.info("  Synthetic rows in CSV by label  : %s", label_counts)
    log.info("  Synthetic rows in CSV by source : %s", source_counts)

    return {
        "synth_total": len(synth),
        "synth_found_in_csv": found_in_csv,
        "synth_missing_from_csv": missing_from_csv,
        "synth_label_counts": label_counts,
        "synth_source_counts": source_counts,
    }


# ---------------------------------------------------------------------------
# Step 3: Exact-duplicate detection
# ---------------------------------------------------------------------------

def detect_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log.info("─" * 60)
    log.info("STEP 3 — Exact-duplicate detection (MD5 on normalised text)")

    df = df.copy()
    df["_hash"] = df["text"].apply(_md5)

    dup_mask = df.duplicated(subset=["_hash"], keep=False)
    exact_dups_df = df[dup_mask].copy()
    n_total_with_dups = len(exact_dups_df)
    n_unique_dup_hashes = exact_dups_df["_hash"].nunique()
    n_to_remove = n_total_with_dups - n_unique_dup_hashes  # rows that are extra copies

    log.info("  Rows involved in exact duplication  : %d", n_total_with_dups)
    log.info("  Unique hash clusters (exact)        : %d", n_unique_dup_hashes)
    log.info("  Rows to remove (extra copies)       : %d", n_to_remove)

    # Deduplicate: keep first occurrence
    df_deduped = df.drop_duplicates(subset=["_hash"], keep="first").copy()
    log.info("  Rows after exact dedup              : %d", len(df_deduped))

    return df_deduped, {
        "exact_dup_rows": n_total_with_dups,
        "exact_dup_clusters": n_unique_dup_hashes,
        "exact_rows_removed": n_to_remove,
        "rows_after_exact_dedup": len(df_deduped),
    }


# ---------------------------------------------------------------------------
# Step 4: Near-duplicate detection (TF-IDF cosine, threshold 0.85)
# ---------------------------------------------------------------------------

def detect_near_duplicates(
    df: pd.DataFrame,
    threshold: float = NEAR_DUP_THRESHOLD,
) -> tuple[pd.DataFrame, dict]:
    """
    Uses TF-IDF char n-gram vectorisation + cosine similarity to detect
    near-duplicate pairs.  Returns deduplicated DataFrame and stats.

    Strategy for large N:
      - Vectorise all texts at once.
      - Process in row-batches of 500 to avoid OOM on cosine_similarity.
      - For each row i, mark rows j > i as duplicates if sim >= threshold.
    """
    log.info("─" * 60)
    log.info("STEP 4 — Near-duplicate detection (TF-IDF cosine, threshold=%.2f)", threshold)

    df = df.reset_index(drop=True)
    texts = df["text"].astype(str).tolist()
    n = len(texts)
    log.info("  Vectorising %d texts …", n)

    vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
        dtype=np.float32,
    )
    X = vec.fit_transform(texts)
    log.info("  TF-IDF matrix shape: %s", X.shape)

    # --- Find near-dup pairs -------------------------------------------
    BATCH = 200  # rows per batch (cosine_similarity is O(n²) memory)
    near_dup_pairs: list[tuple[int, int, float]] = []
    to_drop: set[int] = set()

    log.info("  Scanning for near-duplicate pairs (batch_size=%d) …", BATCH)
    for start in range(0, n, BATCH):
        end = min(start + BATCH, n)
        batch_sims = cosine_similarity(X[start:end], X)  # shape (batch, n)

        for local_i, global_i in enumerate(range(start, end)):
            if global_i in to_drop:
                continue
            row = batch_sims[local_i]
            # Look only at j > global_i to avoid double-counting
            matches = np.where((row > threshold) & (np.arange(n) > global_i))[0]
            for j in matches:
                if j not in to_drop:
                    near_dup_pairs.append((global_i, int(j), float(row[j])))
                    to_drop.add(int(j))

        if (start // BATCH) % 5 == 0:
            log.info("    … processed rows %d–%d, near-dup pairs so far: %d", start, end - 1, len(near_dup_pairs))

    log.info("  Near-duplicate pairs found        : %d", len(near_dup_pairs))
    log.info("  Rows to drop (near-dup secondary) : %d", len(to_drop))

    # Show sample pairs
    if near_dup_pairs:
        log.info("  Sample near-dup pairs (first 5):")
        for i, j, sim in near_dup_pairs[:5]:
            log.info(
                "    [%d] vs [%d]  sim=%.4f\n      A: %s\n      B: %s",
                i, j, sim,
                texts[i][:100],
                texts[j][:100],
            )

    df_deduped = df.drop(index=list(to_drop)).reset_index(drop=True)
    log.info("  Rows after near-dup dedup         : %d", len(df_deduped))

    return df_deduped, {
        "near_dup_pairs": len(near_dup_pairs),
        "near_dup_rows_dropped": len(to_drop),
        "rows_after_near_dedup": len(df_deduped),
    }


# ---------------------------------------------------------------------------
# Step 5: Split-straddling leakage audit (on original data, before dedup)
# ---------------------------------------------------------------------------

def audit_split_straddling(df_original: pd.DataFrame) -> dict:
    """
    Reconstruct an 80/20 stratified split on the ORIGINAL (pre-dedup) data
    with seed=42 (the seed used throughout this pipeline) and count exact
    duplicate pairs that straddle the split boundary.
    """
    log.info("─" * 60)
    log.info("STEP 5 — Split-straddling leakage audit")

    df = df_original.copy()
    df["_hash"] = df["text"].apply(_md5)
    df = df.reset_index(drop=True)

    # Reconstruct 80/20 stratified split
    train_idx, test_idx = train_test_split(
        df.index,
        test_size=TEST_SIZE,
        stratify=df["label"],
        random_state=SPLIT_SEED,
    )
    train_set = set(train_idx)
    test_set  = set(test_idx)

    train_hashes = df.loc[list(train_set), "_hash"]
    test_hashes  = df.loc[list(test_set),  "_hash"]

    # Find hashes that appear in BOTH train and test
    train_hash_set = set(train_hashes)
    test_hash_set  = set(test_hashes)
    straddling_hashes = train_hash_set & test_hash_set

    # Count total rows involved in straddling
    straddling_rows_in_train = int(train_hashes.isin(straddling_hashes).sum())
    straddling_rows_in_test  = int(test_hashes.isin(straddling_hashes).sum())

    log.info("  Original rows           : %d  (train=%d, test=%d)",
             len(df), len(train_set), len(test_set))
    log.info("  Straddling hash clusters: %d", len(straddling_hashes))
    log.info("  Straddling rows in train: %d", straddling_rows_in_train)
    log.info("  Straddling rows in test : %d  ← leakage count", straddling_rows_in_test)

    # Detailed view of straddling examples (first 3)
    if straddling_hashes:
        log.info("  Sample straddling texts (first 3):")
        count = 0
        for h in list(straddling_hashes)[:3]:
            examples = df[df["_hash"] == h]["text"].tolist()
            log.info("    Hash %s ... : %d copies | text[:80]: %s", h[:8], len(examples), examples[0][:80])
            count += 1

    return {
        "train_size": len(train_set),
        "test_size":  len(test_set),
        "straddling_clusters": len(straddling_hashes),
        "straddling_in_train": straddling_rows_in_train,
        "straddling_in_test":  straddling_rows_in_test,
    }


# ---------------------------------------------------------------------------
# Step 6: Fresh stratified split on deduped data
# ---------------------------------------------------------------------------

def apply_fresh_split(df: pd.DataFrame) -> pd.DataFrame:
    log.info("─" * 60)
    log.info("STEP 6 — Fresh stratified 80/20 split on deduped data (seed=%d)", SPLIT_SEED)

    df = df.copy()
    train_idx, test_idx = train_test_split(
        df.index,
        test_size=TEST_SIZE,
        stratify=df["label"],
        random_state=SPLIT_SEED,
    )
    df["split"] = "train"
    df.loc[test_idx, "split"] = "test"

    train_dist = df[df["split"] == "train"]["label"].value_counts().to_dict()
    test_dist  = df[df["split"] == "test"]["label"].value_counts().to_dict()
    log.info("  Train rows: %d | label dist: %s", len(train_idx), train_dist)
    log.info("  Test rows : %d | label dist: %s", len(test_idx), test_dist)

    return df


# ---------------------------------------------------------------------------
# Step 7: Write report
# ---------------------------------------------------------------------------

def write_report(
    original_count: int,
    synth_stats: dict,
    exact_stats: dict,
    near_stats: dict,
    straddle_stats: dict,
    final_count: int,
    train_count: int,
    test_count: int,
) -> str:
    lines = [
        "# Module 1 Deduplication & Leakage Audit Report",
        "",
        f"**Generated by**: `scripts/audit_and_dedup.py`",
        "",
        "---",
        "",
        "## Dataset Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Original row count | {original_count:,} |",
        f"| Synthetic records in JSON | {synth_stats['synth_total']} |",
        f"| Synthetic rows found verbatim in CSV | {synth_stats['synth_found_in_csv']} |",
        f"| Synthetic rows dropped during balancing | {synth_stats['synth_missing_from_csv']} |",
        "",
        "---",
        "",
        "## Exact Duplicates",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Rows involved in exact duplication | {exact_stats['exact_dup_rows']:,} |",
        f"| Unique duplicate clusters | {exact_stats['exact_dup_clusters']:,} |",
        f"| Extra copies removed | {exact_stats['exact_rows_removed']:,} |",
        f"| Rows after exact dedup | {exact_stats['rows_after_exact_dedup']:,} |",
        "",
        "---",
        "",
        "## Near-Duplicates (TF-IDF cosine, threshold = 0.85)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Near-duplicate pairs found | {near_stats['near_dup_pairs']:,} |",
        f"| Secondary rows removed | {near_stats['near_dup_rows_dropped']:,} |",
        f"| Rows after near-dup dedup | {near_stats['rows_after_near_dedup']:,} |",
        "",
        "---",
        "",
        "## Split-Straddling Leakage (on ORIGINAL pre-dedup data)",
        "",
        "> Reconstructed 80/20 stratified split (seed=42) on original data to measure",
        "> how many duplicate rows would have straddled train/test — the true leakage.",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Train set size | {straddle_stats['train_size']:,} |",
        f"| Test set size | {straddle_stats['test_size']:,} |",
        f"| Straddling duplicate clusters | {straddle_stats['straddling_clusters']:,} |",
        f"| Straddling rows leaked into test | **{straddle_stats['straddling_in_test']:,}** |",
        f"| Straddling rows in train | {straddle_stats['straddling_in_train']:,} |",
        "",
        "---",
        "",
        "## Final Deduped Dataset",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Original count | {original_count:,} |",
        f"| Total removed (exact + near-dup) | {original_count - final_count:,} |",
        f"| **Final deduped count** | **{final_count:,}** |",
        f"| Train rows | {train_count:,} |",
        f"| Test rows | {test_count:,} |",
        f"| Output file | `data/processed/finbert_text_training_data_deduped.csv` |",
        "",
        "---",
        "",
        "## Notes",
        "",
        "- Split is stratified by label, seed=42, 80/20 ratio.",
        "- Near-dup check used `TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5))`.",
        "- Synthetic rows from `synthetic_batch.json` were cross-referenced by exact text hash.",
        "- The straddling count above is the **actual leakage** in the pre-dedup training run.",
        "- Post-dedup, the fresh split guarantees zero straddling by construction.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("PRISM | Module 1 | Deduplication & Leakage Audit")
    log.info("=" * 60)

    # 1. Load
    df, synth = load_data()
    original_count = len(df)

    # 2. Synthetic cross-reference
    synth_stats = cross_reference_synthetic(df, synth)

    # 3. Split-straddling audit on ORIGINAL data (before any dedup)
    straddle_stats = audit_split_straddling(df)

    # 4. Exact dedup
    df_after_exact, exact_stats = detect_exact_duplicates(df)

    # 5. Near-dup dedup (on already-exact-deduped data)
    df_deduped, near_stats = detect_near_duplicates(df_after_exact)

    # 6. Drop internal hash column, apply fresh split
    df_deduped = df_deduped.drop(columns=["_hash"], errors="ignore")
    df_final = apply_fresh_split(df_deduped)

    final_count = len(df_final)
    train_count = int((df_final["split"] == "train").sum())
    test_count  = int((df_final["split"] == "test").sum())

    # 7. Save deduped CSV
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    log.info("─" * 60)
    log.info("Saved deduped CSV → %s  (%d rows)", OUTPUT_CSV, final_count)

    # 8. Write report
    report_text = write_report(
        original_count=original_count,
        synth_stats=synth_stats,
        exact_stats=exact_stats,
        near_stats=near_stats,
        straddle_stats=straddle_stats,
        final_count=final_count,
        train_count=train_count,
        test_count=test_count,
    )
    REPORT_MD.write_text(report_text, encoding="utf-8")
    log.info("Saved audit report  → %s", REPORT_MD)

    # 9. Print summary table
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  Original count             : %d", original_count)
    log.info("  Synthetic in JSON          : %d  (in CSV: %d)",
             synth_stats["synth_total"], synth_stats["synth_found_in_csv"])
    log.info("  Exact dupes removed        : %d", exact_stats["exact_rows_removed"])
    log.info("  Near-dupes removed         : %d", near_stats["near_dup_rows_dropped"])
    log.info("  LEAKAGE (straddle rows)    : %d rows in test set",
             straddle_stats["straddling_in_test"])
    log.info("  Final deduped count        : %d  (train=%d, test=%d)",
             final_count, train_count, test_count)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
