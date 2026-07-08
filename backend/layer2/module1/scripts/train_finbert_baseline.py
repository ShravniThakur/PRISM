"""
train_finbert_baseline.py
=========================
PRISM | Layer 2 | Module 1 — Text-Based Threat Detection
---------------------------------------------------------
Fine-tunes ProsusAI/finbert for binary classification:
    Label 0 → Legitimate / safe financial communication
    Label 1 → Phishing / fraud / pump-and-dump threat

The final model is saved to ../models/finbert_baseline/.

Prerequisites:
    pip install transformers datasets scikit-learn torch

Usage:
    python train_finbert_baseline.py [options]

    --data-path PATH        Override default CSV path
    --output-dir PATH       Override default model output path
    --epochs N              Number of training epochs (default: 3)
    --batch-size N          Per-device train batch size (default: 16)
    --max-length N          Max token length (default: 256)
    --lr FLOAT              Learning rate (default: 2e-5)
    --eval-split FLOAT      Fraction of data for evaluation (default: 0.15)
    --test-split FLOAT      Fraction of data for test (default: 0.10)
    --seed N                Random seed (default: 42)
    --fp16                  Enable mixed-precision training (requires GPU)
    --no-cuda               Force CPU training

Author : PRISM ML Team
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# Transformers / Datasets — graceful import error
# ---------------------------------------------------------------------------
try:
    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
        set_seed,
    )
except ImportError as exc:
    print(
        f"[ERROR] Missing dependency: {exc}\n"
        "Please run:  pip install transformers datasets scikit-learn torch",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths (resolved relative to THIS script)
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
MODULE1_DIR   = SCRIPT_DIR.parent
DEFAULT_DATA  = MODULE1_DIR / "data" / "processed" / "finbert_text_training_data.csv"
DEFAULT_MODEL_OUT = MODULE1_DIR / "models" / "finbert_baseline"

BASE_MODEL = "ProsusAI/finbert"
ID2LABEL   = {0: "SAFE", 1: "THREAT"}
LABEL2ID   = {"SAFE": 0, "THREAT": 1}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("train_finbert_baseline")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune ProsusAI/finbert for PRISM Module 1 threat classification.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-path",  type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_OUT)
    parser.add_argument("--epochs",     type=int,   default=3)
    parser.add_argument("--batch-size", type=int,   default=16)
    parser.add_argument("--max-length", type=int,   default=256)
    parser.add_argument("--lr",         type=float, default=2e-5)
    parser.add_argument("--eval-split", type=float, default=0.15,
                        help="Fraction of data reserved for validation.")
    parser.add_argument("--test-split", type=float, default=0.10,
                        help="Fraction of data reserved for final test.")
    parser.add_argument("--seed",       type=int,   default=42)
    parser.add_argument("--fp16",       action="store_true",
                        help="Enable FP16 mixed-precision (GPU only).")
    parser.add_argument("--no-cuda",    action="store_true",
                        help="Force CPU even if a GPU is available.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Data loading & splitting
# ---------------------------------------------------------------------------

def load_data(path: Path) -> pd.DataFrame:
    """Load and validate the processed CSV."""
    if not path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found at: {path}\n"
            "Run prepare_text_dataset.py first."
        )

    log.info("Loading dataset from %s …", path)
    df = pd.read_csv(path, dtype={"label": int})

    required_cols = {"text", "label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Sanitise
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() >= 10].copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].reset_index(drop=True)

    dist = df["label"].value_counts().sort_index().to_dict()
    log.info(
        "  Loaded %d rows | Label dist: 0=%d  1=%d",
        len(df),
        dist.get(0, 0),
        dist.get(1, 0),
    )
    return df


def split_data(
    df: pd.DataFrame,
    eval_frac: float,
    test_frac: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified train / validation / test split."""
    # First carve out the test set
    train_val, test = train_test_split(
        df,
        test_size=test_frac,
        stratify=df["label"],
        random_state=seed,
    )
    # Then split train from validation
    val_frac_adjusted = eval_frac / (1.0 - test_frac)
    train, val = train_test_split(
        train_val,
        test_size=val_frac_adjusted,
        stratify=train_val["label"],
        random_state=seed,
    )
    log.info(
        "Split → train: %d | val: %d | test: %d",
        len(train),
        len(val),
        len(test),
    )
    return train, val, test


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def build_hf_datasets(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    tokenizer: "AutoTokenizer",
    max_length: int,
) -> tuple["Dataset", "Dataset", "Dataset"]:
    """Convert pandas DataFrames to Hugging Face Dataset objects."""

    def _tokenise(batch):
        return tokenizer(
            batch["text"],
            padding="max_length",
            truncation=True,
            max_length=max_length,
        )

    def _df_to_dataset(df: pd.DataFrame) -> "Dataset":
        ds = Dataset.from_pandas(df[["text", "label"]].reset_index(drop=True))
        ds = ds.map(_tokenise, batched=True, batch_size=256)
        ds = ds.rename_column("label", "labels")
        ds.set_format(type="torch", columns=["input_ids", "attention_mask", "token_type_ids", "labels"])
        return ds

    log.info("Tokenising datasets (max_length=%d) …", max_length)
    train_ds = _df_to_dataset(train_df)
    val_ds   = _df_to_dataset(val_df)
    test_ds  = _df_to_dataset(test_df)
    log.info("Tokenisation complete.")
    return train_ds, val_ds, test_ds


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(eval_pred) -> dict:
    """
    Compute precision, recall, F1 (macro) and accuracy.
    Called by Trainer at each evaluation step.
    """
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="macro", zero_division=0
    )
    accuracy = (predictions == labels).mean()

    return {
        "accuracy":  round(float(accuracy),  4),
        "f1_macro":  round(float(f1),         4),
        "precision": round(float(precision),  4),
        "recall":    round(float(recall),     4),
    }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def build_training_args(
    output_dir: Path,
    num_epochs: int,
    batch_size: int,
    lr: float,
    fp16: bool,
    seed: int,
) -> "TrainingArguments":
    """Construct HuggingFace TrainingArguments."""
    logs_dir = output_dir / "logs"
    checkpoints_dir = output_dir / "checkpoints"

    return TrainingArguments(
        output_dir=str(checkpoints_dir),
        logging_dir=str(logs_dir),

        # ── Training schedule ───────────────────────────────────────────
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=lr,
        weight_decay=0.01,
        warmup_ratio=0.06,
        lr_scheduler_type="cosine",

        # ── Evaluation ──────────────────────────────────────────────────
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,

        # ── Logging ────────────────────────────────────────────────────
        logging_steps=50,
        report_to="none",          # set to "wandb" or "tensorboard" if desired

        # ── Reproducibility ────────────────────────────────────────────
        seed=seed,
        data_seed=seed,

        # ── Performance ────────────────────────────────────────────────
        fp16=fp16,
        dataloader_num_workers=0,  # Windows-safe default; increase on Linux
        group_by_length=True,      # speeds up training by batching similar lengths

        # ── Checkpointing ──────────────────────────────────────────────
        save_total_limit=2,        # keep only the 2 best checkpoints
    )


def evaluate_on_test(
    trainer: "Trainer",
    test_ds: "Dataset",
    test_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Run final evaluation on the held-out test set and print a full report."""
    log.info("Running final evaluation on test set …")
    pred_output = trainer.predict(test_ds)
    preds = np.argmax(pred_output.predictions, axis=-1)
    labels = pred_output.label_ids

    report = classification_report(
        labels, preds,
        target_names=["SAFE (0)", "THREAT (1)"],
        digits=4,
    )
    cm = confusion_matrix(labels, preds)

    log.info("\n%s\nClassification Report:\n%s", "=" * 60, report)
    log.info("Confusion Matrix:\n%s", cm)

    # Save report to file
    report_path = output_dir / "test_evaluation_report.txt"
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("PRISM Module 1 — FinBERT Baseline Test Evaluation\n")
        fh.write("=" * 60 + "\n\n")
        fh.write(report)
        fh.write("\n\nConfusion Matrix (rows=Actual, cols=Predicted):\n")
        fh.write(str(cm) + "\n")
    log.info("Test report saved → %s", report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # ── Reproducibility ──────────────────────────────────────────────────
    set_seed(args.seed)

    # ── Device setup ─────────────────────────────────────────────────────
    if args.no_cuda:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    device = "cuda" if (torch.cuda.is_available() and not args.no_cuda) else "cpu"
    log.info("Training device: %s", device.upper())

    if args.fp16 and device == "cpu":
        log.warning("--fp16 requested but no GPU found; disabling FP16.")
        args.fp16 = False

    # ── Output dirs ──────────────────────────────────────────────────────
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (args.output_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("PRISM | Module 1 | FinBERT Baseline Training")
    log.info("=" * 60)
    log.info("Base model  : %s", BASE_MODEL)
    log.info("Data path   : %s", args.data_path)
    log.info("Output dir  : %s", args.output_dir)
    log.info("Epochs      : %d", args.epochs)
    log.info("Batch size  : %d", args.batch_size)
    log.info("Max length  : %d", args.max_length)
    log.info("Learning rate: %.2e", args.lr)
    log.info("FP16        : %s", args.fp16)

    # ── Load data ────────────────────────────────────────────────────────
    df = load_data(args.data_path)
    train_df, val_df, test_df = split_data(
        df,
        eval_frac=args.eval_split,
        test_frac=args.test_split,
        seed=args.seed,
    )

    # ── Tokeniser ────────────────────────────────────────────────────────
    log.info("Loading tokeniser from %s …", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    train_ds, val_ds, test_ds = build_hf_datasets(
        train_df, val_df, test_df, tokenizer, args.max_length
    )

    # ── Model ────────────────────────────────────────────────────────────
    log.info("Loading model from %s …", BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=2,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,   # FinBERT has 3-class head; we replace it
    )
    model.to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.info(
        "Model loaded: %d total params | %d trainable.",
        total_params,
        trainable_params,
    )

    # ── Training arguments ───────────────────────────────────────────────
    training_args = build_training_args(
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        fp16=args.fp16,
        seed=args.seed,
    )

    # ── Trainer ──────────────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=2,
                early_stopping_threshold=0.001,
            )
        ],
    )

    # ── Train ────────────────────────────────────────────────────────────
    log.info("Starting training …")
    train_result = trainer.train()
    log.info(
        "Training complete. "
        "Total steps: %d | Runtime: %.1fs | Samples/s: %.2f",
        train_result.global_step,
        train_result.metrics.get("train_runtime", 0),
        train_result.metrics.get("train_samples_per_second", 0),
    )

    # ── Save final model ─────────────────────────────────────────────────
    log.info("Saving final model to %s …", args.output_dir)
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    # Save training metrics
    trainer.log_metrics("train", train_result.metrics)
    trainer.save_metrics("train", train_result.metrics)

    # ── Final evaluation ─────────────────────────────────────────────────
    evaluate_on_test(trainer, test_ds, test_df, args.output_dir)

    # ── Validate model loads correctly ───────────────────────────────────
    log.info("Verifying saved model loads correctly …")
    try:
        _verify_model = AutoModelForSequenceClassification.from_pretrained(
            str(args.output_dir)
        )
        log.info("  Model verification: ✓ PASSED")
    except Exception as exc:  # noqa: BLE001
        log.error("  Model verification: ✗ FAILED — %s", exc)

    log.info("=" * 60)
    log.info("Done. Final model saved → %s", args.output_dir)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
