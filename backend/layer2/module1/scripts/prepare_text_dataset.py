"""
prepare_text_dataset.py
=======================
PRISM | Layer 2 | Module 1 — Text-Based Threat Detection
---------------------------------------------------------
Pipeline:
  1. Asynchronously generate synthetic labelled text via a mock LLM API
     (plug in Gemini / Claude credentials to go live).
  2. Load real datasets:
       - FinancialPhraseBank-v1.0  → Label 0 (safe / neutral financial text)
       - Ling.csv                  → mixed (use existing 'label' column)
       - Nigerian_Fraud.csv        → Label 1 (fraud)
  3. Merge, deduplicate, balance 50/50, shuffle, and save to
       ../data/processed/finbert_text_training_data.csv

Usage:
  python prepare_text_dataset.py [--samples-per-persona N] [--seed S]

Author : PRISM ML Team
"""

import asyncio
import json
import logging
import os
import random
import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Resolve paths relative to THIS script, not the CWD
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
MODULE1_DIR  = SCRIPT_DIR.parent
DATA_DIR     = MODULE1_DIR / "data"
RAW_DIR      = DATA_DIR / "raw"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
PROCESSED_DIR = DATA_DIR / "processed"

FINBANK_PATH  = RAW_DIR / "FinancialPhraseBank-v1.0" / "Sentences_AllAgree.txt"
LING_PATH     = RAW_DIR / "PhishingEmailDataset" / "Ling.csv"
FRAUD_PATH    = RAW_DIR / "PhishingEmailDataset" / "Nigerian_Fraud.csv"
SYNTH_PATH    = SYNTHETIC_DIR / "synthetic_batch.json"
OUTPUT_PATH   = PROCESSED_DIR / "finbert_text_training_data.csv"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("prepare_text_dataset")

# ---------------------------------------------------------------------------
# Synthetic data templates
# Persona definitions contain weighted text templates.  A real implementation
# would replace `_mock_llm_call` with an async call to the Gemini or Claude API.
# ---------------------------------------------------------------------------

PERSONA_TEMPLATES: dict[str, dict[str, Any]] = {
    "phishing_email": {
        "label": 1,
        "source_type": "email",
        "bodies": [
            (
                "Dear Investor, SEBI has detected suspicious activity in your Demat account "
                "(ID: {demat}). To avoid immediate suspension, click here to verify your "
                "identity and submit your OTP within 2 hours: https://sebi-secure-verify.{tld}/auth"
            ),
            (
                "This is an official communication from the National Stock Exchange of India. "
                "Your trading account requires KYC re-verification. Failure to comply before "
                "{deadline} will result in a permanent trading ban. Verify now: "
                "https://nse-kyc-update.{tld}/{token}"
            ),
            (
                "BSE Compliance Notice: Your portfolio shows irregular short-selling activity. "
                "Legal action will be initiated unless you verify your Demat credentials at "
                "https://bse-compliance.{tld}/user/{demat} within 24 hours."
            ),
            (
                "Zerodha Security Alert 🚨 — We have detected a login from an unrecognised "
                "device. If this was not you, immediately reset your password and confirm "
                "your OTP at https://zerodha-secure.{tld}/reset?session={token}"
            ),
            (
                "Groww Account Notice: Your mutual fund SIP has been flagged for review. "
                "SEBI regulation 45(b) requires you to re-submit your PAN verification at "
                "https://groww-compliance.{tld}/kyc?ref={token}"
            ),
        ],
        "slots": lambda: {
            "demat": f"IN30{random.randint(100000000, 999999999)}",
            "deadline": random.choice(["31 March 2026", "15 April 2026", "1 May 2026"]),
            "tld": random.choice(["net.in", "org.co", "info.in", "co.gov-in.xyz"]),
            "token": f"{random.randint(1000000, 9999999):07x}",
        },
    },
    "pump_and_dump": {
        "label": 1,
        "source_type": "social_media",
        "bodies": [
            (
                "🚀🚀 BIG ALERT! {ticker} is about to EXPLODE 💥 Get in NOW before the "
                "institutional buyers scoop it all up! Target: ₹{target} in 48 hrs! "
                "This is your LAST CHANCE 🔥 DM for insider tip. #StockAlert #NSE #BullRun"
            ),
            (
                "⚡ INSIDER TIP ⚡ {ticker} just got a mega order from a Fortune 500 company. "
                "Stock will 10X by Friday! Buy at ₹{price}, exit at ₹{target}. "
                "Already up {pct}% today! Don't miss the bus 🚌💰 #MultiBagger #StockMarket"
            ),
            (
                "📢 BREAKING: Promoters of {ticker} secretly buying shares in bulk! "
                "Circuit breaker alert! 💹 Enter below ₹{price}, set SL at {sl}. "
                "This is a ₹{target} stock! Verified source 👆 #TradingAlert #PumpAlert"
            ),
            (
                "🔴 URGENT 🔴 {ticker} about to hit upper circuit in next 2 sessions! "
                "SEBI approved FPO coming next week — stock is MASSIVELY undervalued. "
                "BUY NOW! ₹{price} → ₹{target} guaranteed return! 🤑 Join our premium group: t.me/{group}"
            ),
            (
                "💎 GEM STOCK ALERT 💎\nScrip: {ticker}\nCMP: ₹{price}\nTarget: ₹{target} (48 hrs)\n"
                "Upside: {pct}% 🚀\nReason: Institutional accumulation + Q4 beat incoming!\n"
                "⏳ Time-sensitive. Share with your group! #TipOfTheDay"
            ),
        ],
        "slots": lambda: {
            "ticker": random.choice([
                "NOVA FINTECH", "ALPHA MICRO", "DELTA TRADE", "SIGMA CAPITAL",
                "BHARAT VEND", "KIRAN TECH", "SURYA INFRA", "LOTUS PHARM"
            ]),
            "price":  random.randint(18, 120),
            "target": random.randint(180, 850),
            "pct":    random.randint(12, 48),
            "sl":     random.randint(12, 90),
            "group":  f"stockgurus_{random.randint(100, 999)}",
        },
    },
    "voice_call_transcript": {
        "label": 1,
        "source_type": "voice_transcript",
        "bodies": [
            (
                "Caller: Good afternoon, I am calling from SEBI Enforcement Division. "
                "Your Demat account {demat} has been flagged for suspicious penny stock activity. "
                "To avoid freezing of your account please confirm your 6-digit OTP that SEBI has "
                "just sent to your registered mobile. Victim: Okay, it's {otp}. Caller: Thank you. "
                "Your account is now under review. Do not discuss this call with anyone."
            ),
            (
                "Agent: Namaste, I'm calling on behalf of NSE Investor Protection Cell. "
                "We have received a complaint that your trading account was used for circular "
                "trading on {date}. You need to provide your Demat OTP for identity verification "
                "to avoid a First Information Report (FIR). Please share the OTP received on "
                "your Aadhaar-linked mobile. Victim: It is {otp}. Agent: Confirmed, case closed."
            ),
            (
                "Caller: Hello sir, SEBI's SCORES portal has logged a fraud alert against your "
                "broker account. I am Officer {name}, badge number {badge}. To protect your funds "
                "you must transfer ₹{amount} to our designated escrow account immediately and we "
                "will return it once the audit is complete. Do you have your net-banking OTP ready?"
            ),
            (
                "Representative: We are from Zerodha Risk Management. Our system detected that "
                "your account was logged into from {city}. As a security protocol, please verify "
                "your TPIN and confirm the last 4 digits of your bank account linked to your "
                "Zerodha profile. This call is being recorded for compliance."
            ),
            (
                "Caller: Sir, I am from BSE investor helpdesk. Your Demat account shows a "
                "pending refund of ₹{amount} from an old IPO allotment. To process this refund "
                "we need you to share the OTP sent by CDSL to your mobile ending in XX{last4}. "
                "Victim: It is {otp}. Caller: Thank you, the refund will reflect in 2-3 days."
            ),
        ],
        "slots": lambda: {
            "demat":  f"IN30{random.randint(100000000, 999999999)}",
            "otp":    f"{random.randint(100000, 999999)}",
            "date":   random.choice(["12 June 2026", "3 May 2026", "28 April 2026"]),
            "name":   random.choice(["Rajiv Sharma", "Anand Mehta", "Priya Nair", "Rajan Tiwari"]),
            "badge":  f"SEBI{random.randint(1000, 9999)}",
            "amount": random.randint(10000, 250000),
            "city":   random.choice(["Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]),
            "last4":  f"{random.randint(10, 99)}",
        },
    },
    "legitimate_finance": {
        "label": 0,
        "source_type": "email",
        "bodies": [
            (
                "Dear Client, your margin utilisation for {date} stands at {pct}% of the "
                "available collateral. Your free margin is ₹{amount}. Please ensure adequate "
                "funds to avoid margin calls. Contact your relationship manager for queries."
            ),
            (
                "Daily Market Commentary — {date}\nNifty 50 closed at {nifty} ({change:+.2f}%). "
                "Sensex settled at {sensex}. FII net inflows: ₹{fii} crore. "
                "Sectoral leaders: {sector}. Broader markets underperformed with mid-cap index "
                "down {mid:.2f}%."
            ),
            (
                "Your SIP of ₹{amount} for {fund} has been successfully processed on {date}. "
                "Units allotted: {units:.4f} at NAV of ₹{nav:.2f}. "
                "Cumulative investment: ₹{cum}. Current value: ₹{cval}. XIRR: {xirr:.2f}%."
            ),
            (
                "CDSL Depository Notice: Your annual maintenance charge of ₹{amc} has been "
                "debited from your linked bank account on {date}. Receipt number: {rcpt}. "
                "For queries visit https://www.cdslindia.com or call 1800-200-5533."
            ),
            (
                "Q4 FY2026 Results Update: {company} reported revenue of ₹{rev} crore "
                "(YoY {rev_chg:+.1f}%) and PAT of ₹{pat} crore ({pat_chg:+.1f}% YoY). "
                "EBITDA margin came in at {ebitda:.1f}%. The board declared a dividend of "
                "₹{div} per share. Next earnings call: {call_date}."
            ),
        ],
        "slots": lambda: {
            "date":     random.choice(["7 July 2026", "8 July 2026", "9 July 2026"]),
            "pct":      round(random.uniform(30, 85), 1),
            "amount":   random.randint(5000, 500000),
            "nifty":    round(random.uniform(22000, 26000), 2),
            "change":   round(random.uniform(-1.5, 1.5), 2),
            "sensex":   round(random.uniform(72000, 87000), 2),
            "fii":      round(random.uniform(-3000, 5000), 2),
            "sector":   random.choice(["IT, FMCG", "Banking, Auto", "Metal, Pharma"]),
            "mid":      round(random.uniform(0.1, 0.8), 2),
            "fund":     random.choice(["Mirae Asset Large Cap", "HDFC Flexicap", "Axis Bluechip"]),
            "units":    random.uniform(10, 200),
            "nav":      round(random.uniform(30, 600), 2),
            "cum":      random.randint(10000, 1000000),
            "cval":     random.randint(11000, 1200000),
            "xirr":     round(random.uniform(8, 22), 2),
            "amc":      random.choice([300, 400, 500, 600]),
            "rcpt":     f"CDSL{random.randint(10000000, 99999999)}",
            "company":  random.choice(["Infosys Ltd", "HDFC Bank", "Reliance Industries", "TCS"]),
            "rev":      random.randint(5000, 200000),
            "rev_chg":  round(random.uniform(-5, 25), 1),
            "pat":      random.randint(500, 50000),
            "pat_chg":  round(random.uniform(-10, 40), 1),
            "ebitda":   round(random.uniform(12, 35), 1),
            "div":      round(random.uniform(2, 30), 2),
            "call_date": random.choice(["22 July 2026", "28 July 2026"]),
        },
    },
}


# ---------------------------------------------------------------------------
# Batched generation constants
# ---------------------------------------------------------------------------

# Number of samples requested in a single LLM API call.
# Keeping this at 20-25 avoids context-window truncation and stays well
# within the token limits of Gemini Flash / Claude Haiku.
BATCH_SIZE: int = 20

# Seconds to sleep between consecutive API calls for each persona batch.
# Gemini free tier: 15 RPM / 1M TPM.  Claude free: 5 RPM.
# A 2-second delay is conservative but safe for both providers.
RATE_LIMIT_SLEEP: float = 2.0


# ---------------------------------------------------------------------------
# Mock / Real LLM client  (single-sample)
# ---------------------------------------------------------------------------

async def _mock_llm_call(persona_key: str, slots: dict) -> str:
    """
    Mock async LLM call for ONE sample.
    Replace this body with a real API call when credentials are available.

    -- Gemini (google-generativeai >= 0.7) --
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        _gemini = genai.GenerativeModel("gemini-1.5-flash")

        async def _mock_llm_call(persona_key, slots):
            prompt = (
                f"Generate ONE realistic example of a '{persona_key}' message "
                f"for Indian financial fraud detection training.\n"
                f"Context variables: {slots}\n"
                f"Return ONLY the message text, no JSON, no labels."
            )
            response = await _gemini.generate_content_async(prompt)
            return response.text.strip()

    -- Claude (anthropic >= 0.28) --
        import anthropic
        _claude = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        async def _mock_llm_call(persona_key, slots):
            msg = await _claude.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=512,
                messages=[{"role": "user", "content":
                    f"Generate ONE '{persona_key}' example. Variables: {slots}. "
                    f"Return only the message text."
                }],
            )
            return msg.content[0].text.strip()
    """
    await asyncio.sleep(0)          # yield to event loop; replace with real await
    persona = PERSONA_TEMPLATES[persona_key]
    template = random.choice(persona["bodies"])
    try:
        return template.format(**slots)
    except KeyError:
        return template             # return raw template on slot mismatch


# ---------------------------------------------------------------------------
# Mock / Real LLM client  (batch call — 20-25 samples per call)
# ---------------------------------------------------------------------------

async def _mock_llm_batch_call(
    persona_key: str,
    batch_size: int,
) -> list[dict]:
    """
    Request *batch_size* samples from the LLM in a single API call.

    The mock implementation generates each sample independently and
    returns them in the same list[dict] format expected by the caller.

    When using a real LLM, replace the body with a single prompt that
    asks the model to return a JSON array of *batch_size* items:

    -- Gemini batch prompt template --
        prompt = (
            f"Generate exactly {batch_size} distinct, realistic examples "
            f"of the '{persona_key}' fraud type targeting Indian retail "
            f"investors. Each example must impersonate SEBI, NSE, BSE, "
            f"Zerodha, or Groww in a unique way.\n\n"
            f"Return ONLY a JSON array with {batch_size} objects, each "
            f"having a single key 'text'. No markdown, no commentary."
        )
        response = await _gemini.generate_content_async(prompt)
        raw = response.text.strip().lstrip('`').rstrip('`')
        parsed = json.loads(raw)    # list of {"text": "..."}
        persona = PERSONA_TEMPLATES[persona_key]
        return [
            {"text": item["text"], "label": persona["label"],
             "source_type": persona["source_type"]}
            for item in parsed
        ]

    -- Claude batch prompt template --
        msg = await _claude.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=batch_size * 200,
            messages=[{"role": "user", "content":
                f"Generate exactly {batch_size} distinct '{persona_key}' "
                f"examples for PRISM fraud detection. "
                f"Return a JSON array of objects with key 'text' only."
            }],
        )
        parsed = json.loads(msg.content[0].text)
        ...
    """
    persona = PERSONA_TEMPLATES[persona_key]
    tasks = [
        _mock_llm_call(persona_key, persona["slots"]())
        for _ in range(batch_size)
    ]
    texts = await asyncio.gather(*tasks)
    return [
        {
            "text": text.strip(),
            "label": persona["label"],
            "source_type": persona["source_type"],
        }
        for text in texts
    ]


# ---------------------------------------------------------------------------
# Batched generation loop
# ---------------------------------------------------------------------------

async def generate_synthetic_batch(
    samples_per_persona: int = 200,
    batch_size: int = BATCH_SIZE,
    rate_limit_sleep: float = RATE_LIMIT_SLEEP,
    seed: int = 42,
) -> list[dict]:
    """
    Generate *samples_per_persona* labelled records per persona using a
    controlled batching loop.

    Strategy
    --------
    For each persona:
        - Divide *samples_per_persona* into ceil(samples_per_persona / batch_size)
          batches of at most *batch_size* samples each.
        - Fire one LLM API call per batch (avoids context-window truncation).
        - Sleep *rate_limit_sleep* seconds between batches to respect
          Gemini / Claude TPS and TPM rate limits (prevents HTTP 429).

    With the defaults (200 samples, batch_size=20):
        10 batches × 20 samples × 4 personas = 800 total records.

    Parameters
    ----------
    samples_per_persona : Total samples to generate per persona.
    batch_size          : Max samples per individual API call (20-25 recommended).
    rate_limit_sleep    : Seconds to wait between API calls (default: 2.0).
    seed                : Random seed for reproducibility.

    Returns
    -------
    list[dict]  All generated records, [{"text", "label", "source_type"}, ...].
    """
    import math

    random.seed(seed)

    n_batches = math.ceil(samples_per_persona / batch_size)
    total_expected = samples_per_persona * len(PERSONA_TEMPLATES)

    log.info(
        "Starting batched synthetic generation:"
    )
    log.info(
        "  Personas          : %d  (%s)",
        len(PERSONA_TEMPLATES),
        ", ".join(PERSONA_TEMPLATES.keys()),
    )
    log.info("  Samples/persona   : %d", samples_per_persona)
    log.info("  Batch size        : %d samples/call", batch_size)
    log.info("  Batches/persona   : %d", n_batches)
    log.info("  Rate-limit sleep  : %.1fs between batches", rate_limit_sleep)
    log.info("  Total expected    : %d records", total_expected)

    all_records: list[dict] = []

    for persona_key in PERSONA_TEMPLATES:
        persona_records: list[dict] = []
        remaining = samples_per_persona

        log.info(
            "  [%s] Starting %d batches ...",
            persona_key, n_batches,
        )

        for batch_idx in range(n_batches):
            # Last batch may be smaller than batch_size
            this_batch = min(batch_size, remaining)
            if this_batch <= 0:
                break

            log.info(
                "    Batch %d/%d — requesting %d samples ...",
                batch_idx + 1, n_batches, this_batch,
            )

            try:
                batch_records = await _mock_llm_batch_call(
                    persona_key=persona_key,
                    batch_size=this_batch,
                )
            except Exception as exc:                    # noqa: BLE001
                log.error(
                    "    Batch %d/%d failed for persona '%s': %s — skipping.",
                    batch_idx + 1, n_batches, persona_key, exc,
                )
                batch_records = []

            persona_records.extend(batch_records)
            remaining -= this_batch

            log.info(
                "    Batch %d/%d done — %d new records, %d total for '%s'.",
                batch_idx + 1, n_batches,
                len(batch_records),
                len(persona_records),
                persona_key,
            )

            # Rate-limit guard: sleep between batches (skip after last batch)
            if batch_idx < n_batches - 1 and remaining > 0:
                log.debug(
                    "    Sleeping %.1fs to respect API rate limits ...",
                    rate_limit_sleep,
                )
                await asyncio.sleep(rate_limit_sleep)

        all_records.extend(persona_records)
        log.info(
            "  [%s] Complete — %d / %d samples generated.",
            persona_key, len(persona_records), samples_per_persona,
        )

    log.info(
        "Batched generation complete: %d total records (expected %d).",
        len(all_records), total_expected,
    )
    return all_records


def save_synthetic_batch(records: list[dict], out_path: Path) -> None:
    """
    Atomically write all records to *out_path* as a JSON array.

    The file is always **overwritten** (not appended) so the downstream
    load_synthetic() and merge_and_balance() always consume exactly the
    records produced by the most recent generation run.  Re-runs are
    idempotent when the same seed is used.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    log.info(
        "Saved synthetic batch (%d records) -> %s",
        len(records), out_path,
    )


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------

def load_financial_phrasebank(path: Path) -> pd.DataFrame:
    """
    Loads Sentences_AllAgree.txt.
    Format:  <sentence>@<sentiment>   (positive | negative | neutral)
    We treat ALL of these as Label 0 (safe financial language).
    """
    if not path.exists():
        log.warning("FinancialPhraseBank not found at %s — skipping.", path)
        return pd.DataFrame(columns=["text", "label", "source_type"])

    log.info("Loading FinancialPhraseBank from %s …", path)
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if "@" not in line:
                continue
            # Some lines have the delimiter appearing inside the sentence;
            # split from the right to get the sentiment tag robustly.
            text, _sentiment = line.rsplit("@", 1)
            text = text.strip()
            if text:
                rows.append({
                    "text": text,
                    "label": 0,
                    "source_type": "financial_news",
                })
    df = pd.DataFrame(rows)
    log.info("  → %d rows loaded from FinancialPhraseBank.", len(df))
    return df


def load_phishing_ling(path: Path) -> pd.DataFrame:
    """
    Loads Ling.csv.
    Columns expected: subject, body, label  (0 = ham, 1 = phishing/spam)
    We use subject + body as the text field and map label 1 → threat.
    """
    if not path.exists():
        log.warning("Ling.csv not found at %s — skipping.", path)
        return pd.DataFrame(columns=["text", "label", "source_type"])

    log.info("Loading Ling.csv from %s …", path)
    try:
        df_raw = pd.read_csv(
            path,
            usecols=["subject", "body", "label"],
            dtype={"label": int},
            on_bad_lines="skip",
            low_memory=False,
        )
    except ValueError:
        # Older pandas
        df_raw = pd.read_csv(
            path,
            usecols=["subject", "body", "label"],
            dtype={"label": int},
            error_bad_lines=False,
            warn_bad_lines=True,
            low_memory=False,
        )

    # Combine subject + body into a single text field
    df_raw["subject"] = df_raw["subject"].fillna("").astype(str)
    df_raw["body"] = df_raw["body"].fillna("").astype(str)
    df_raw["text"] = (df_raw["subject"] + " " + df_raw["body"]).str.strip()
    df_raw["source_type"] = "email"

    df = df_raw[["text", "label", "source_type"]].copy()
    log.info("  → %d rows loaded from Ling.csv (label dist: %s).",
             len(df), df["label"].value_counts().to_dict())
    return df


def load_nigerian_fraud(path: Path) -> pd.DataFrame:
    """
    Loads Nigerian_Fraud.csv.
    Columns expected: sender, receiver, date, subject, body, urls, label
    All rows are labelled 1 (fraud).
    """
    if not path.exists():
        log.warning("Nigerian_Fraud.csv not found at %s — skipping.", path)
        return pd.DataFrame(columns=["text", "label", "source_type"])

    log.info("Loading Nigerian_Fraud.csv from %s …", path)
    try:
        df_raw = pd.read_csv(
            path,
            usecols=["subject", "body"],
            on_bad_lines="skip",
            low_memory=False,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load Nigerian_Fraud.csv cleanly (%s). Trying fallback.", exc)
        df_raw = pd.read_csv(
            path,
            usecols=["subject", "body"],
            error_bad_lines=False,
            low_memory=False,
        )

    df_raw["subject"] = df_raw["subject"].fillna("").astype(str)
    df_raw["body"] = df_raw["body"].fillna("").astype(str)
    df_raw["text"] = (df_raw["subject"] + " " + df_raw["body"]).str.strip()
    df_raw["label"] = 1
    df_raw["source_type"] = "email"

    df = df_raw[["text", "label", "source_type"]].copy()
    log.info("  → %d rows loaded from Nigerian_Fraud.csv.", len(df))
    return df


def load_synthetic(path: Path) -> pd.DataFrame:
    """Loads the synthetic_batch.json file generated above."""
    if not path.exists():
        log.warning("Synthetic batch not found at %s — skipping.", path)
        return pd.DataFrame(columns=["text", "label", "source_type"])

    log.info("Loading synthetic batch from %s …", path)
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)
    df = pd.DataFrame(records)
    log.info("  → %d rows loaded from synthetic batch.", len(df))
    return df


# ---------------------------------------------------------------------------
# Merge & balance pipeline
# ---------------------------------------------------------------------------

def merge_and_balance(
    dfs: list[pd.DataFrame],
    seed: int = 42,
) -> pd.DataFrame:
    """
    Concatenates all dataframes, cleans text, removes duplicates,
    enforces a strict 50/50 class balance, and shuffles.

    Returns a balanced DataFrame with columns: text, label, source_type
    """
    log.info("Merging %d source dataframes …", len(dfs))
    combined = pd.concat(dfs, ignore_index=True)
    log.info("  Combined size before cleaning: %d rows.", len(combined))

    # ── 1. Text cleaning ───────────────────────────────────────────────────
    combined["text"] = combined["text"].astype(str).str.strip()
    combined = combined[combined["text"].str.len() >= 20]  # drop near-empty rows
    combined["label"] = combined["label"].astype(int)

    # ── 2. Deduplicate on exact text ──────────────────────────────────────
    before_dedup = len(combined)
    combined = combined.drop_duplicates(subset=["text"])
    log.info(
        "  Dropped %d duplicate rows → %d unique rows.",
        before_dedup - len(combined),
        len(combined),
    )

    # ── 3. Validate labels ─────────────────────────────────────────────────
    combined = combined[combined["label"].isin([0, 1])]
    dist = combined["label"].value_counts().to_dict()
    log.info("  Label distribution before balancing: %s", dist)

    # ── 4. 50/50 balance ──────────────────────────────────────────────────
    safe_df   = combined[combined["label"] == 0]
    threat_df = combined[combined["label"] == 1]

    min_count = min(len(safe_df), len(threat_df))
    if min_count == 0:
        raise ValueError(
            "One of the classes has zero samples after deduplication. "
            "Check your data sources and synthetic generation."
        )

    safe_df   = safe_df.sample(n=min_count, random_state=seed)
    threat_df = threat_df.sample(n=min_count, random_state=seed)

    balanced = pd.concat([safe_df, threat_df], ignore_index=True)
    log.info(
        "  Balanced to %d rows per class (%d total).",
        min_count,
        len(balanced),
    )

    # ── 5. Shuffle ────────────────────────────────────────────────────────
    balanced = balanced.sample(frac=1, random_state=seed).reset_index(drop=True)

    return balanced[["text", "label", "source_type"]]


def save_processed(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    log.info(
        "Saved processed dataset (%d rows) → %s",
        len(df),
        out_path,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the FinBERT text training dataset for PRISM Module 1."
    )
    parser.add_argument(
        "--samples-per-persona",
        type=int,
        default=200,
        help=(
            "Total synthetic samples to generate per persona (default: 200). "
            "With --batch-size 20 this means 10 batches per persona, "
            "800 total records across 4 personas."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=(
            f"Samples requested per individual LLM API call (default: {BATCH_SIZE}). "
            "Keep between 20-25 to avoid context-window truncation."
        ),
    )
    parser.add_argument(
        "--rate-limit-sleep",
        type=float,
        default=RATE_LIMIT_SLEEP,
        help=(
            f"Seconds to sleep between batch API calls (default: {RATE_LIMIT_SLEEP}). "
            "Increase if you hit HTTP 429 Too Many Requests."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--skip-synthetic",
        action="store_true",
        help="Skip synthetic generation and use existing synthetic_batch.json.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    log.info("=" * 60)
    log.info("PRISM | Module 1 | Text Dataset Preparation")
    log.info("=" * 60)

    # ── Step 1: Synthetic generation ──────────────────────────────────────
    if args.skip_synthetic and SYNTH_PATH.exists():
        log.info("--skip-synthetic set; using existing %s", SYNTH_PATH)
    else:
        records = await generate_synthetic_batch(
            samples_per_persona=args.samples_per_persona,
            batch_size=args.batch_size,
            rate_limit_sleep=args.rate_limit_sleep,
            seed=args.seed,
        )
        save_synthetic_batch(records, SYNTH_PATH)

    # ── Step 2: Load all data sources ──────────────────────────────────────
    df_phrasebank = load_financial_phrasebank(FINBANK_PATH)
    df_ling       = load_phishing_ling(LING_PATH)
    df_fraud      = load_nigerian_fraud(FRAUD_PATH)
    df_synth      = load_synthetic(SYNTH_PATH)

    # ── Step 3: Merge, balance, save ──────────────────────────────────────
    df_final = merge_and_balance(
        [df_phrasebank, df_ling, df_fraud, df_synth],
        seed=args.seed,
    )

    save_processed(df_final, OUTPUT_PATH)

    # ── Summary ───────────────────────────────────────────────────────────
    log.info("-" * 60)
    log.info("Final dataset summary:")
    log.info("  Total rows  : %d", len(df_final))
    log.info("  Label 0 (safe)   : %d", (df_final["label"] == 0).sum())
    log.info("  Label 1 (threat) : %d", (df_final["label"] == 1).sum())
    log.info("  Source types: %s", df_final["source_type"].value_counts().to_dict())
    log.info("=" * 60)
    log.info("Done. Output: %s", OUTPUT_PATH)


if __name__ == "__main__":
    asyncio.run(main())
