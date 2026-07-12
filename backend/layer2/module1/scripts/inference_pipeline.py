"""
inference_pipeline.py
=====================
PRISM | Layer 2 | Module 1 -- Text-Based Threat Detection
Step 5: Inference Pipeline
----------------------------------------------------------
Orchestrates the full Module 1 analysis for a single incoming message:

    1. Text normalisation
    2. FinBERT binary classification  (text_threat_probability)
    3. URL / typo-squat analysis      (url_analysis)
    4. Score fusion & penalty logic   (final_text_score)
    5. Human-readable reason generation

Public API
----------
    TextThreatAnalyzer          -- class; load once, call many times
    TextThreatAnalyzer.analyze_message(text, source_type) -> dict
    quick_analyze(text, source_type) -> dict  -- convenience wrapper

Output contract (always returned, even on error)
-------------------------------------------------
{
    "final_text_score"    : float,     # 0.0 -- 1.0  combined threat score
    "model_confidence"    : float,     # 0.0 -- 1.0  raw FinBERT confidence
    "url_analysis"        : {          # verbatim from url_analyzer.analyze_urls()
        "urls_found"          : list[str],
        "suspicious_urls"     : list[dict],
        "is_url_threat"       : bool
    },
    "human_readable_reason": str,      # one-sentence plain-English explanation
    "source_type"          : str,      # echo of input source_type
    "model_used"           : str,      # which model weights were loaded
    "error"                : str|None  # populated only on unexpected failures
}

Integration Notes
-----------------
* TextThreatAnalyzer is **not** thread-safe at construction time; build it
  once in your app startup and share the instance (inference is read-only).
* analyze_message() is declared `async` so it can be awaited from an
  async API framework (FastAPI, etc.).  Internally, the CPU-bound FinBERT
  inference is dispatched to a thread-pool executor so it does not block
  the event loop.
* The URL analyzer is pure-Python / zero-dependency and runs in the same
  thread without blocking.

Usage
-----
    # Synchronous
    import asyncio
    from inference_pipeline import TextThreatAnalyzer

    analyzer = TextThreatAnalyzer()
    result = asyncio.run(
        analyzer.analyze_message(
            text="Verify your SEBI account at https://sebii.gov.in/kyc",
            source_type="email"
        )
    )
    print(result["final_text_score"])   # e.g. 0.97

    # Async (inside an async framework)
    analyzer = TextThreatAnalyzer()
    result = await analyzer.analyze_message(text=..., source_type=...)

Prerequisites
-------------
    pip install transformers torch

Author : PRISM ML Team
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("inference_pipeline")

# ---------------------------------------------------------------------------
# Path resolution (all relative to THIS file)
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
MODULE1_DIR  = SCRIPT_DIR.parent
LOCAL_MODEL  = MODULE1_DIR / "models" / "finbert_baseline"
FALLBACK_MODEL = "ProsusAI/finbert"

# ---------------------------------------------------------------------------
# Import url_analyzer -- handles both "scripts" is on sys.path and not
# ---------------------------------------------------------------------------
try:
    from url_analyzer import analyze_urls                    # when cwd == scripts/
except ImportError:
    sys.path.insert(0, str(SCRIPT_DIR))
    from url_analyzer import analyze_urls                    # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Transformers -- graceful import guard
# ---------------------------------------------------------------------------
try:
    import torch
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        pipeline as hf_pipeline,
    )
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False
    log.warning(
        "transformers / torch not installed.  "
        "TextThreatAnalyzer will operate in URL-only mode.  "
        "Run:  pip install transformers torch"
    )

# ---------------------------------------------------------------------------
# Configuration knobs
# ---------------------------------------------------------------------------

# Label returned by FinBERT (or the fine-tuned head) that represents a threat.
# Adjust if your training used a different label string.
THREAT_LABELS: frozenset[str] = frozenset({"THREAT", "negative", "LABEL_1", "1"})

# Token length passed to FinBERT.  Must match what was used during training.
MAX_TOKEN_LENGTH: int = 256

# Score fusion weights & penalty constants
# When both signals fire, the final score is blended using these weights.
# Raise URL_PENALTY to make URL presence more decisive.
FINBERT_WEIGHT: float = 0.55   # weight of text model score in fusion
URL_WEIGHT:     float = 0.45   # weight of URL signal in fusion

# Hard-ceiling boost: if a suspicious URL is found AND the text score is
# already above BOOST_TRIGGER, snap the final score to at least BOOST_FLOOR.
BOOST_TRIGGER:  float = 0.45   # minimum text score to activate URL boost
BOOST_FLOOR:    float = 0.92   # floor applied when boost activates

# Threshold above which we call the message a threat in the reason string.
THREAT_THRESHOLD: float = 0.60

# Thread-pool size for running blocking FinBERT inference off the event loop.
_EXECUTOR_WORKERS: int = 1

# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

# Patterns compiled once at import time for efficiency.
_RE_WHITESPACE   = re.compile(r"\s+")
_RE_HTML_TAGS    = re.compile(r"<[^>]+>")
_RE_REPEATED_CH  = re.compile(r"(.)\1{4,}")   # e.g. "!!!!!!!" -> "!!!!"
_RE_URLS_FOR_NORM = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)


def normalise_text(text: str, *, preserve_urls: bool = True) -> str:
    """
    Clean and normalise raw input text before passing it to FinBERT.

    Steps applied (in order):
        1. Strip HTML tags
        2. Normalise Unicode whitespace
        3. Collapse runs of 5+ repeated characters to 4
        4. Strip leading/trailing whitespace

    URL strings are intentionally preserved by default so that the URL
    analyzer (which runs on the *original* text) still has something to
    work with even after normalisation.

    Parameters
    ----------
    text          : Raw input (email body, social post, transcript, etc.)
    preserve_urls : If False, strip URL strings entirely (not recommended
                    for inference -- set True and let url_analyzer handle them).

    Returns
    -------
    str  Cleaned text ready for tokenisation.
    """
    if not isinstance(text, str):
        return ""

    # 1. Remove HTML
    cleaned = _RE_HTML_TAGS.sub(" ", text)

    # 2. Normalise whitespace (tabs, newlines, zero-width spaces, etc.)
    cleaned = _RE_WHITESPACE.sub(" ", cleaned)

    # 3. Collapse obnoxious character repetitions  (!!!!!!! -> !!!!)
    cleaned = _RE_REPEATED_CH.sub(r"\1\1\1\1", cleaned)

    # 4. Strip
    cleaned = cleaned.strip()

    return cleaned


# ---------------------------------------------------------------------------
# Score fusion helpers
# ---------------------------------------------------------------------------

def _fuse_scores(
    text_score: float,
    url_is_threat: bool,
    suspicious_url_count: int,
) -> float:
    """
    Combine the FinBERT text score with the URL threat signal into a
    single `final_text_score` in [0.0, 1.0].

    Fusion logic (applied in priority order):
        1. Hard boost: If text_score >= BOOST_TRIGGER and at least one
           suspicious URL exists, snap final score to >= BOOST_FLOOR.
           This captures the "phishing text + deceptive link" case with
           maximum precision.
        2. Weighted blend: Otherwise, blend text_score with a URL signal
           (0.0 or 1.0) using FINBERT_WEIGHT / URL_WEIGHT.
        3. Clamp to [0.01, 0.99] -- never output exactly 0 or 1 to avoid
           misleading the downstream system.

    Parameters
    ----------
    text_score           : Raw FinBERT threat probability (0.0 -- 1.0).
    url_is_threat        : True if any suspicious URL was found.
    suspicious_url_count : Number of suspicious URLs detected.

    Returns
    -------
    float  Final fused threat score, clamped to [0.01, 0.99].
    """
    url_signal = 1.0 if url_is_threat else 0.0

    # -- 1. Hard boost when both signals agree --
    if url_is_threat and text_score >= BOOST_TRIGGER:
        # Scale boost floor up slightly per additional suspicious URL (capped)
        extra = min(suspicious_url_count - 1, 3) * 0.01
        fused = max(text_score, BOOST_FLOOR + extra)
    else:
        # -- 2. Weighted blend --
        # If the text is overwhelmingly malicious (like a vishing/OTP stealing script),
        # do not aggressively penalize it just for lacking a URL.
        if text_score > 0.85:
            fused = text_score
        else:
            fused = (FINBERT_WEIGHT * text_score) + (URL_WEIGHT * url_signal)

    # -- 3. Clamp --
    return round(max(0.01, min(0.99, fused)), 4)


def _build_reason(
    final_score: float,
    text_score: float,
    url_analysis: dict,
    source_type: str,
) -> str:
    """
    Generate a concise, human-readable explanation of the analysis result.

    The reason covers:
    - Overall threat/safe determination
    - Source type context
    - Specific URL spoof targets (if any)
    - Confidence level

    Parameters
    ----------
    final_score  : Fused final threat score.
    text_score   : Raw FinBERT confidence.
    url_analysis : Output dict from url_analyzer.analyze_urls().
    source_type  : e.g. "email", "social_media", "voice_transcript".

    Returns
    -------
    str  One or two sentence plain-English reason.
    """
    is_threat    = final_score >= THREAT_THRESHOLD
    suspicious   = url_analysis.get("suspicious_urls", [])
    url_is_threat = url_analysis.get("is_url_threat", False)

    source_label = {
        "email":            "email",
        "social_media":     "social media post",
        "voice_transcript": "voice call transcript",
        "financial_news":   "financial news article",
    }.get(source_type, source_type or "message")

    # ---- Threat path ----
    if is_threat:
        confidence_desc = (
            "very high" if final_score >= 0.90 else
            "high"      if final_score >= 0.75 else
            "moderate"
        )

        text_signal = (
            "Highly manipulative language consistent with phishing detected"
            if text_score >= 0.75
            else "Language patterns suggest potential financial fraud"
        )

        if url_is_threat and suspicious:
            # Name all spoofed targets
            targets = sorted({s["target_spoofed"] for s in suspicious
                               if not s["target_spoofed"].startswith("[")})
            ip_spoof = any(s["target_spoofed"].startswith("[") for s in suspicious)

            url_parts: list[str] = []
            if targets:
                url_parts.append(
                    "alongside a deceptive typo-squatted URL targeting "
                    + ", ".join(f"'{t}'" for t in targets)
                )
            if ip_spoof:
                url_parts.append("a raw IP address used to conceal the true destination")

            url_detail = " and ".join(url_parts) + "." if url_parts else "."

            return (
                f"{confidence_desc.capitalize()} probability of phishing in this {source_label}: "
                f"{text_signal} {url_detail}"
            )
        else:
            return (
                f"{confidence_desc.capitalize()} probability of phishing in this {source_label}: "
                f"{text_signal}. "
                f"No deceptive URLs detected; threat is driven by message content alone."
            )

    # ---- URL-only threat (low text score but suspicious URL present) ----
    if url_is_threat and suspicious:
        targets = sorted({s["target_spoofed"] for s in suspicious
                           if not s["target_spoofed"].startswith("[")})
        target_str = ", ".join(f"'{t}'" for t in targets) if targets else "a legitimate domain"
        return (
            f"Low text-model threat signal for this {source_label}, but suspicious URL(s) "
            f"spoofing {target_str} were detected. Manual review recommended."
        )

    # ---- Clean path ----
    confidence_desc = (
        "very low" if final_score < 0.20 else
        "low"      if final_score < 0.40 else
        "below threshold"
    )
    return (
        f"Threat probability is {confidence_desc} for this {source_label}. "
        f"Text content appears consistent with legitimate financial communication "
        f"and no deceptive URLs were found."
    )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TextThreatAnalyzer:
    """
    Encapsulates the full Module 1 inference logic.

    Load once at startup; share the instance across requests.

    Parameters
    ----------
    model_path      : Path to the fine-tuned FinBERT model directory.
                      Defaults to ../models/finbert_baseline/.
                      Falls back to ProsusAI/finbert if the directory is empty.
    device          : "cpu", "cuda", or "auto" (default).
                      "auto" selects CUDA if available, otherwise CPU.
    max_length      : Maximum token length for FinBERT (must match training).
    executor_workers: Number of threads in the internal ThreadPoolExecutor
                      used to run blocking inference off the async event loop.

    Example
    -------
    >>> analyzer = TextThreatAnalyzer()
    >>> import asyncio
    >>> result = asyncio.run(
    ...     analyzer.analyze_message(
    ...         text="Verify your Demat OTP at https://sebii.gov.in/kyc",
    ...         source_type="email"
    ...     )
    ... )
    >>> result["is_url_threat"]   # from url_analysis sub-dict
    True
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        device: str = "auto",
        max_length: int = MAX_TOKEN_LENGTH,
        executor_workers: int = _EXECUTOR_WORKERS,
    ) -> None:
        self._max_length = max_length
        self._classifier = None       # HuggingFace pipeline object
        self._model_used: str = "none (URL-only mode)"
        self._executor   = ThreadPoolExecutor(
            max_workers=executor_workers,
            thread_name_prefix="finbert_worker",
        )

        # Resolve device
        if device == "auto":
            self._device = (
                0 if (_TRANSFORMERS_AVAILABLE and __import__("torch").cuda.is_available())
                else -1                        # HF pipeline: -1 = CPU
            )
        else:
            self._device = 0 if device == "cuda" else -1

        # Resolve model path
        if model_path is not None:
            self._model_path = Path(model_path)
        else:
            self._model_path = LOCAL_MODEL

        self._load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """
        Load the FinBERT classifier.

        Priority:
            1. Fine-tuned weights at self._model_path  (if directory is non-empty)
            2. ProsusAI/finbert from HuggingFace Hub   (fallback / testing)
            3. URL-only mode                           (if transformers not installed)
        """
        if not _TRANSFORMERS_AVAILABLE:
            log.warning(
                "transformers not installed -- running in URL-only mode.  "
                "Install with:  pip install transformers torch"
            )
            return

        model_source = self._resolve_model_source()
        log.info("Loading FinBERT model from: %s", model_source)

        t0 = time.perf_counter()
        try:
            self._classifier = hf_pipeline(
                task="text-classification",
                model=model_source,
                tokenizer=model_source,
                device=self._device,
                max_length=self._max_length,
                truncation=True,
                padding=True,
            )
            self._model_used = str(model_source)
            elapsed = time.perf_counter() - t0
            device_name = "GPU" if self._device >= 0 else "CPU"
            log.info(
                "Model loaded in %.2fs on %s: %s",
                elapsed, device_name, model_source,
            )
        except Exception as exc:                        # noqa: BLE001
            log.error(
                "Failed to load model from %r: %s  -- falling back to URL-only mode.",
                model_source, exc,
            )
            self._classifier = None
            self._model_used = f"load_error:{exc}"

    def _resolve_model_source(self) -> str:
        """
        Return the model identifier to load (local path or HuggingFace Hub ID).

        Uses the local fine-tuned model if the directory contains a
        config.json (i.e. training has been run).  Otherwise falls back
        to the upstream ProsusAI/finbert weights.
        """
        local_config = self._model_path / "config.json"
        if self._model_path.is_dir() and local_config.exists():
            log.info(
                "Found local fine-tuned model at %s", self._model_path
            )
            return str(self._model_path)
        else:
            log.warning(
                "Local model not found at %s (run train_finbert_baseline.py first). "
                "Falling back to ProsusAI/finbert for testing.",
                self._model_path,
            )
            return FALLBACK_MODEL

    # ------------------------------------------------------------------
    # Internal: FinBERT inference (blocking -- run in executor)
    # ------------------------------------------------------------------

    def _run_finbert(self, text: str) -> tuple[float, str]:
        """
        Run FinBERT on *text* and return (threat_probability, raw_label).

        The method is synchronous / blocking and is designed to be
        dispatched to a ThreadPoolExecutor from the async caller.

        Returns
        -------
        (threat_probability, raw_label)
            threat_probability : float in [0.0, 1.0] -- probability that
                                 the text is a threat (Label 1 / THREAT).
            raw_label          : The string label returned by the model.

        Notes
        -----
        - If the classifier is not loaded, returns (0.0, "NO_MODEL").
        - The mapping from model label -> threat probability handles both
          the fine-tuned head (SAFE/THREAT) and the raw ProsusAI/finbert
          head (positive/negative/neutral) transparently.
        """
        if self._classifier is None:
            return 0.0, "NO_MODEL"

        try:
            output = self._classifier(
                text,
                truncation=True,
                max_length=self._max_length,
            )
            # HF pipeline returns a list[dict] with 'label' and 'score'
            result = output[0] if isinstance(output, list) else output
            raw_label: str = str(result.get("label", "UNKNOWN")).upper()
            confidence: float = float(result.get("score", 0.5))

            # Map label to threat probability
            if raw_label in {l.upper() for l in THREAT_LABELS}:
                threat_prob = confidence
            else:
                # Complementary: if model is confident it's SAFE, threat is low
                threat_prob = 1.0 - confidence

            return round(threat_prob, 4), raw_label

        except Exception as exc:                        # noqa: BLE001
            log.error("FinBERT inference error: %s", exc, exc_info=True)
            return 0.5, "INFERENCE_ERROR"              # neutral fallback

    # ------------------------------------------------------------------
    # Public: async analysis
    # ------------------------------------------------------------------

    async def analyze_message(
        self,
        text: str,
        source_type: str = "unknown",
    ) -> dict[str, Any]:
        """
        Analyse a single message for financial fraud / phishing threat.

        This coroutine is safe to await from any async framework (FastAPI,
        aiohttp, etc.).  FinBERT inference is dispatched to a thread-pool
        executor so the event loop remains unblocked.

        Parameters
        ----------
        text        : Raw message text (email body, social post, transcript).
        source_type : One of "email", "social_media", "voice_transcript",
                      "financial_news", or any custom string.

        Returns
        -------
        dict  Structured output conforming to the PRISM Module 1 contract.
              See module docstring for the full schema.

        Raises
        ------
        Does NOT raise.  All exceptions are caught and surfaced in the
        "error" key of the returned dict.
        """
        t_start = time.perf_counter()

        # ── Initialise output with safe defaults ─────────────────────────
        output: dict[str, Any] = {
            "final_text_score":     0.0,
            "model_confidence":     0.0,
            "url_analysis": {
                "urls_found":      [],
                "suspicious_urls": [],
                "is_url_threat":   False,
            },
            "human_readable_reason": "",
            "source_type":           source_type,
            "model_used":            self._model_used,
            "error":                 None,
        }

        if not isinstance(text, str) or not text.strip():
            output["human_readable_reason"] = "Empty or invalid input -- no analysis performed."
            output["error"] = "empty_input"
            return output

        try:
            # ── Step 1: Normalise text ──────────────────────────────────
            clean_text = normalise_text(text, preserve_urls=True)
            log.debug("Normalised text (%d chars): %.120s ...", len(clean_text), clean_text)

            # ── Step 2 & 3: Run FinBERT + URL analyzer concurrently ─────
            #
            # FinBERT is CPU/GPU-bound and blocking -- dispatch to thread pool.
            # url_analyzer is pure Python and fast -- run directly.
            #
            # Both are kicked off before either result is awaited so they
            # overlap on the wall clock whenever the executor has a free thread.
            loop = asyncio.get_event_loop()

            finbert_future = loop.run_in_executor(
                self._executor,
                self._run_finbert,
                clean_text,
            )

            # url_analyzer is non-blocking; we can run it directly in the
            # event loop while FinBERT runs in the executor thread.
            url_result: dict = analyze_urls(text)        # original text (pre-normalisation)

            # Await FinBERT result
            text_score, raw_label = await finbert_future

            log.info(
                "FinBERT -> label=%s  confidence=%.4f | URL threat=%s  suspicious=%d",
                raw_label, text_score,
                url_result["is_url_threat"],
                len(url_result["suspicious_urls"]),
            )

            # ── Step 4: Score fusion ────────────────────────────────────
            final_score = _fuse_scores(
                text_score=text_score,
                url_is_threat=url_result["is_url_threat"],
                suspicious_url_count=len(url_result["suspicious_urls"]),
            )

            # ── Step 5: Build human-readable reason ─────────────────────
            reason = _build_reason(
                final_score=final_score,
                text_score=text_score,
                url_analysis=url_result,
                source_type=source_type,
            )

            # ── Assemble output ─────────────────────────────────────────
            output["final_text_score"]     = final_score
            output["model_confidence"]     = text_score
            output["url_analysis"]         = url_result
            output["human_readable_reason"] = reason

        except Exception as exc:                        # noqa: BLE001
            log.error("Unexpected error in analyze_message: %s", exc, exc_info=True)
            output["error"] = str(exc)
            output["human_readable_reason"] = (
                "Analysis failed due to an internal error. "
                "See the 'error' field for details."
            )

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
        log.info(
            "analyze_message complete: final_score=%.4f  elapsed=%sms",
            output["final_text_score"], elapsed_ms,
        )
        return output

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Cleanly shut down the internal thread-pool executor."""
        log.info("Shutting down TextThreatAnalyzer executor ...")
        self._executor.shutdown(wait=True)

    def __repr__(self) -> str:
        return (
            f"TextThreatAnalyzer("
            f"model={self._model_used!r}, "
            f"device={'GPU' if self._device >= 0 else 'CPU'}, "
            f"max_length={self._max_length})"
        )


# ---------------------------------------------------------------------------
# Convenience wrapper (for scripts / notebooks)
# ---------------------------------------------------------------------------

_DEFAULT_ANALYZER: TextThreatAnalyzer | None = None


def quick_analyze(
    text: str,
    source_type: str = "unknown",
    *,
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Module-level convenience function.

    Creates (or reuses) a singleton TextThreatAnalyzer and runs a
    synchronous analysis.  Useful for quick scripts and notebooks where
    you don't want to manage the class lifecycle manually.

    Parameters
    ----------
    text        : Raw input text.
    source_type : One of "email", "social_media", "voice_transcript", etc.
    model_path  : Optional override for the model directory.

    Returns
    -------
    dict  Same contract as TextThreatAnalyzer.analyze_message().

    Example
    -------
    >>> from inference_pipeline import quick_analyze
    >>> result = quick_analyze(
    ...     "Dear investor, SEBI has blocked your account. Verify at sebii.gov.in",
    ...     source_type="email"
    ... )
    >>> print(result["final_text_score"])
    """
    global _DEFAULT_ANALYZER
    if _DEFAULT_ANALYZER is None:
        _DEFAULT_ANALYZER = TextThreatAnalyzer(model_path=model_path)
    return asyncio.run(
        _DEFAULT_ANALYZER.analyze_message(text=text, source_type=source_type)
    )


# ---------------------------------------------------------------------------
# CLI demo / smoke-test
# ---------------------------------------------------------------------------

_DEMO_CASES: list[dict] = [
    {
        "label":       "Typosquat SEBI phishing email",
        "source_type": "email",
        "text": (
            "Dear Investor, SEBI has detected suspicious trading activity on your Demat "
            "account IN30812345678. To avoid immediate suspension, please verify your "
            "identity and submit your 6-digit OTP within 2 hours: "
            "https://sebii.gov.in/verify?token=8a3f9c1d"
        ),
    },
    {
        "label":       "Pump-and-dump WhatsApp post with IP URL",
        "source_type": "social_media",
        "text": (
            "URGENT ALERT! NOVA FINTECH (NSE: NOVFT) is about to EXPLODE 🚀🚀 "
            "Get in NOW before institutions scoop it all up! Target: Rs.420 in 48 hrs!! "
            "LAST CHANCE 🔥 Full insider details: http://203.0.113.45/tip"
        ),
    },
    {
        "label":       "Fake SEBI officer voice transcript",
        "source_type": "voice_transcript",
        "text": (
            "Caller: Good afternoon, I am calling from SEBI Enforcement Division. "
            "Your Demat account IN30987654321 has been flagged for irregular penny-stock "
            "trading on 3 July 2026. To prevent an FIR being filed, please confirm "
            "the 6-digit OTP that SEBI has sent to your registered mobile immediately."
        ),
    },
    {
        "label":       "Legitimate daily market commentary",
        "source_type": "email",
        "text": (
            "Daily Market Commentary -- 8 July 2026. "
            "Nifty 50 closed at 24,312 (+0.42%). FII net inflow: Rs.2,140 crore. "
            "Sectoral outperformers: IT, FMCG. Your SIP of Rs.5,000 for HDFC Flexi Cap "
            "has been processed successfully. Visit https://groww.in/portfolio for details."
        ),
    },
    {
        "label":       "Legit CDSL annual maintenance email",
        "source_type": "email",
        "text": (
            "Your annual Demat account maintenance charge of Rs.450 has been debited on "
            "8 July 2026. Receipt number: CDSL20260708-48291. "
            "For queries contact 1800-200-5533 or visit https://www.cdslindia.com."
        ),
    },
]


async def _run_demo() -> None:
    """Run the built-in demo cases and print results."""
    import json
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    SEP  = "=" * 72
    DASH = "-" * 72

    print("\n" + SEP)
    print("  PRISM Module 1 -- Inference Pipeline Demo")
    print(SEP)

    analyzer = TextThreatAnalyzer()
    print(f"  Analyzer: {analyzer!r}\n")

    for i, case in enumerate(_DEMO_CASES, 1):
        print(f"\n{DASH}")
        print(f"  Case {i}: {case['label']}")
        print(f"  Source : {case['source_type']}")
        print(f"  Input  : {case['text'][:100]}{'...' if len(case['text']) > 100 else ''}")
        print()

        result = await analyzer.analyze_message(
            text=case["text"],
            source_type=case["source_type"],
        )

        # Pretty print relevant fields
        print(f"  final_text_score    : {result['final_text_score']}")
        print(f"  model_confidence    : {result['model_confidence']}")
        print(f"  is_url_threat       : {result['url_analysis']['is_url_threat']}")
        susp = result["url_analysis"]["suspicious_urls"]
        if susp:
            for s in susp:
                print(
                    f"    -> spoofs '{s['target_spoofed']}' "
                    f"(score={s['similarity_score']})"
                )
        print(f"  human_readable_reason:")
        print(f"    \"{result['human_readable_reason']}\"")
        if result.get("error"):
            print(f"  [ERROR]: {result['error']}")

    print("\n" + SEP)
    print("  Demo complete.")
    print(SEP + "\n")

    analyzer.shutdown()


if __name__ == "__main__":
    asyncio.run(_run_demo())
