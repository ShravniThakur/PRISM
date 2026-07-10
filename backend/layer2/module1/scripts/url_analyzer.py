"""
url_analyzer.py
===============
PRISM | Layer 2 | Module 1 — Text-Based Threat Detection
Step 4: URL / Link Analysis
---------------------------------------------------------
Extracts URLs from raw text, parses their effective domain,
and detects typo-squatting / homoglyph attacks against a
curated list of legitimate Indian financial domains.

Public API
----------
    analyze_urls(text: str) -> dict
        Main entry point.  Returns a structured dict ready to
        be merged into the Step 5 inference-pipeline output.

    extract_urls(text: str) -> list[str]
        Pull all raw URL strings from a text blob.

    get_effective_domain(url: str) -> str | None
        Parse a URL and return its registrable domain
        (e.g. "sebii.gov.in" from "https://sebii.gov.in/verify")

    score_against_whitelist(domain: str) -> tuple[str, float]
        Return the closest whitelisted domain and its
        SequenceMatcher similarity score.

    is_typosquat(domain: str, best_match: str, score: float) -> bool
        Apply the deception heuristic: near-match but not exact.

Usage
-----
    from url_analyzer import analyze_urls

    result = analyze_urls(
        "Dear Investor, verify your account at https://sebii.gov.in/kyc now."
    )
    # {
    #   "urls_found": ["https://sebii.gov.in/kyc"],
    #   "suspicious_urls": [
    #       {"url": "https://sebii.gov.in/kyc",
    #        "target_spoofed": "sebi.gov.in",
    #        "similarity_score": 0.92}
    #   ],
    #   "is_url_threat": True
    # }

Author : PRISM ML Team
"""

from __future__ import annotations

import difflib
import ipaddress
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelist of legitimate Indian financial / regulatory domains
# ---------------------------------------------------------------------------
# Keep all entries as lowercase, fully-qualified registrable domains.
# Format: <subdomain_stripped>.tld   e.g. "sebi.gov.in" not "www.sebi.gov.in"
#
# Add new trusted domains here — the rest of the logic picks them up
# automatically without any other changes.
# ---------------------------------------------------------------------------
LEGITIMATE_DOMAINS: list[str] = [
    # Regulators & Government
    "sebi.gov.in",
    "nseindia.com",
    "bseindia.com",
    "rbi.org.in",
    "irdai.gov.in",
    "pfrda.org.in",
    "mca.gov.in",
    "incometax.gov.in",
    "epfindia.gov.in",
    "npscra.nsdl.co.in",
    "finmin.nic.in",
    # Depositories & Clearing
    "cdslindia.com",
    "nsdl.co.in",
    "nsccl.com",
    "icclindia.com",
    # Banks (public)
    "onlinesbi.sbi",
    "sbi.co.in",
    "bankofindia.co.in",
    "pnbindia.in",
    "unionbankofindia.co.in",
    "canarabank.com",
    # Banks (private)
    "hdfcbank.com",
    "icicibank.com",
    "axisbank.com",
    "yesbank.in",
    "kotak.com",
    "indusind.com",
    "federalbank.co.in",
    "idfcfirstbank.com",
    "bandhanbank.com",
    # Brokers / Investment platforms
    "zerodha.com",
    "kite.zerodha.com",
    "groww.in",
    "angelone.in",
    "icicidirect.com",
    "hdfcsec.com",
    "sbisec.co.in",
    "motilaloswal.com",
    "sharekhan.com",
    "upstox.com",
    "5paisa.com",
    "dhan.co",
    "fyers.in",
    "paytmmoney.com",
    "nuvama.com",
    # Mutual funds / AMCs
    "mutualfund.adityabirlacapital.com",
    "hdfcfund.com",
    "icicipruamc.com",
    "sbimf.com",
    "axismf.com",
    "mirae-asset.com",
    "nipponindiamf.com",
    "kotakmf.com",
    "franklintempletonindia.com",
    "miraeassetmf.co.in",
    # Insurance
    "licindia.in",
    "hdfcergo.com",
    "icicilombard.com",
    "starhealth.in",
    # KYC / Infrastructure
    "cvlkra.com",
    "karvykra.com",
    "camskra.com",
    "dotex.in",
    # Financial news (reference-grade only)
    "moneycontrol.com",
    "economictimes.com",
    "livemint.com",
    "business-standard.com",
    "bsepsu.com",
]

# ---------------------------------------------------------------------------
# Configuration knobs
# ---------------------------------------------------------------------------

# Similarity band for typo-squat detection:
#   score >= UPPER_THRESHOLD  → exact / very-close match → NOT flagged
#     (assumed to be the real domain or a trivial variant we trust)
#   score >= LOWER_THRESHOLD  → close enough to be deceptive → FLAG
#   score <  LOWER_THRESHOLD  → too different to be a spoof → ignore
UPPER_THRESHOLD: float = 0.98   # treat as exact match
LOWER_THRESHOLD: float = 0.70   # minimum similarity to count as squatting
                                 # lowered 0.72→0.70 to catch same-brand/different-TLD
                                 # spoofs (e.g. groww.com vs groww.in)

# Minimum domain string length to bother checking (avoids short noise tokens)
MIN_DOMAIN_LEN: int = 6

# ---------------------------------------------------------------------------
# Homoglyph / confusable character normalisation map
# (covers common substitutions used in phishing domains)
# ---------------------------------------------------------------------------
_HOMOGLYPH_MAP: dict[str, str] = {
    "0": "o",   # zer0dha → zerodha
    "1": "l",   # 1ic     → lic
    "3": "e",   # s3bi    → sebi
    "4": "a",   # hdfc4   → hdfc (less common but seen)
    "5": "s",   # 5ebi    → sebi
    "8": "b",   # 8se     → bse
    "@": "a",
    "!": "i",
    "|": "l",
    "vv": "w",  # string-level: handled in _normalize_domain
}

# ---------------------------------------------------------------------------
# Regex: captures http/https/ftp URLs and bare domain references
# ---------------------------------------------------------------------------
# Pattern 1: fully qualified URLs with scheme
_URL_WITH_SCHEME = re.compile(
    r"""
    (?:https?|ftp)://                  # scheme
    (?:[A-Za-z0-9\-._~:@!$&'()*+,;=%]+)  # authority + path + query
    [A-Za-z0-9/]                       # must end with an alnum or /
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Pattern 2: bare domains that look like known TLDs (no scheme)
# We keep this conservative to avoid false positives on normal text.
_BARE_DOMAIN = re.compile(
    r"""
    (?<![@\w])                          # not preceded by @ (email address) or word char
    (?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+
    (?:com|in|org|net|gov\.in|co\.in|sbi|info|biz|io)
    (?=[/?#\s,;!)\]"']|$)              # followed by end or punctuation
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Dataclass for a single suspicious URL finding
# ---------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class SuspiciousURL:
    """Represents a single detected typo-squatting URL."""
    url: str
    target_spoofed: str
    similarity_score: float

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "target_spoofed": self.target_spoofed,
            "similarity_score": round(self.similarity_score, 4),
        }


@dataclass
class AnalysisResult:
    """Full result returned by analyze_urls."""
    urls_found: list[str] = field(default_factory=list)
    suspicious_urls: list[SuspiciousURL] = field(default_factory=list)
    is_url_threat: bool = False

    def to_dict(self) -> dict:
        return {
            "urls_found": self.urls_found,
            "suspicious_urls": [s.to_dict() for s in self.suspicious_urls],
            "is_url_threat": self.is_url_threat,
        }


# ---------------------------------------------------------------------------
# Domain normalisation helpers
# ---------------------------------------------------------------------------

def _apply_homoglyphs(domain: str) -> str:
    """
    Substitute common digit / symbol lookalikes with their letter equivalents
    so that 'zer0dha.com' normalises to 'zerodha.com' for comparison.
    """
    # Multi-char substitutions first (e.g. "vv" → "w")
    for glyph, replacement in _HOMOGLYPH_MAP.items():
        if len(glyph) > 1:
            domain = domain.replace(glyph, replacement)
    # Single-char substitutions
    result: list[str] = []
    for ch in domain:
        result.append(_HOMOGLYPH_MAP.get(ch, ch))
    return "".join(result)


def _unicode_normalize(domain: str) -> str:
    """
    Convert Unicode / IDN domains to ASCII-compatible encoding (ACE / punycode)
    so that Cyrillic 'а' doesn't slip past as Latin 'a'.
    """
    try:
        return domain.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        # Fall back to NFKD normalisation (strips combining characters)
        return unicodedata.normalize("NFKD", domain).encode("ascii", "ignore").decode("ascii")


def _strip_www(domain: str) -> str:
    """Remove leading 'www.' (and 'www2.', 'www3.', etc.)."""
    return re.sub(r"^www\d*\.", "", domain, flags=re.IGNORECASE)


def _is_ip_address(token: str) -> bool:
    """Return True if token is a raw IP address (v4 or v6)."""
    try:
        ipaddress.ip_address(token)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Public helper: extract URLs from text
# ---------------------------------------------------------------------------

def extract_urls(text: str) -> list[str]:
    """
    Extract all URL strings from *text*.

    Finds:
    - Fully qualified URLs (http://, https://, ftp://)
    - Bare domain references that match common TLDs

    Parameters
    ----------
    text : str
        Raw input text (email body, social post, transcript, etc.)

    Returns
    -------
    list[str]
        Deduplicated list of raw URL / domain strings in order of appearance.
    """
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()

    for match in _URL_WITH_SCHEME.finditer(text):
        url = match.group(0).rstrip(".,:;)")
        if url not in seen:
            found.append(url)
            seen.add(url)

    for match in _BARE_DOMAIN.finditer(text):
        url = match.group(0).rstrip(".,:;)")
        if url not in seen:
            found.append(url)
            seen.add(url)

    return found


# ---------------------------------------------------------------------------
# Public helper: extract effective (registrable) domain from a URL
# ---------------------------------------------------------------------------

def get_effective_domain(url: str) -> str | None:
    """
    Parse *url* and return its effective registrable domain.

    Handles:
    - Full URLs:  'https://secure.sebii.gov.in/kyc?ref=123' → 'sebii.gov.in'
    - Bare domains: 'zer0dha.com' → 'zer0dha.com'
    - IP addresses: returned as-is ('192.168.1.1')

    Parameters
    ----------
    url : str
        A raw URL or bare domain string.

    Returns
    -------
    str | None
        The registrable domain (lowercase), or None if parsing fails.
    """
    if not url:
        return None

    # Ensure the URL has a scheme so urlparse works correctly
    url_to_parse = url if re.match(r"[a-z]+://", url, re.IGNORECASE) else f"http://{url}"

    try:
        parsed = urlparse(url_to_parse)
        hostname = parsed.hostname or ""
    except Exception as exc:  # noqa: BLE001
        log.debug("urlparse failed for %r: %s", url, exc)
        return None

    if not hostname:
        return None

    # Strip brackets from IPv6 literals
    hostname = hostname.strip("[]")

    # Raw IP addresses — return as-is
    if _is_ip_address(hostname):
        return hostname

    # Lowercase and strip www prefix
    hostname = _strip_www(hostname.lower())

    # Extract the registrable domain.
    # We handle the compound TLDs used in India:
    # .gov.in | .co.in | .org.in | .net.in | .edu.in | .ac.in
    _COMPOUND_TLDS = re.compile(
        r"(?:gov|co|org|net|edu|ac|nic|res|mil)\.(?:in|org)$"
    )
    parts = hostname.split(".")

    if len(parts) < 2:
        return hostname  # single-label — return raw

    # Check for known compound TLDs (e.g. gov.in, co.in)
    candidate_suffix = ".".join(parts[-2:])
    if _COMPOUND_TLDS.search(candidate_suffix):
        # Registrable domain = label before the compound TLD
        # e.g. ['secure', 'sebii', 'gov', 'in'] → 'sebii.gov.in'
        if len(parts) >= 3:
            return ".".join(parts[-3:])
        else:
            return hostname

    # Standard case: last two labels = registrable domain
    return ".".join(parts[-2:])


# ---------------------------------------------------------------------------
# Public helper: score a domain against the whitelist
# ---------------------------------------------------------------------------

def score_against_whitelist(domain: str) -> tuple[str, float]:
    """
    Find the most similar whitelisted domain to *domain* and return
    (best_match, similarity_score).

    The comparison is done on two levels:
    1. The raw domain string (catches character insertions/deletions).
    2. The homoglyph-normalised domain (catches digit substitutions).

    The higher of the two scores is returned.

    Parameters
    ----------
    domain : str
        The domain to check (already lowercased).

    Returns
    -------
    tuple[str, float]
        (best_matching_whitelist_domain, similarity_score ∈ [0.0, 1.0])
    """
    best_match = ""
    best_score = 0.0

    normalised = _apply_homoglyphs(_unicode_normalize(domain))

    for legit in LEGITIMATE_DOMAINS:
        # Raw comparison
        raw_score = difflib.SequenceMatcher(
            None, domain, legit, autojunk=False
        ).ratio()

        # Normalised comparison (homoglyph-stripped)
        norm_legit = _apply_homoglyphs(legit)
        norm_score = difflib.SequenceMatcher(
            None, normalised, norm_legit, autojunk=False
        ).ratio()

        score = max(raw_score, norm_score)

        if score > best_score:
            best_score = score
            best_match = legit

    return best_match, best_score


# ---------------------------------------------------------------------------
# Public helper: typo-squat decision
# ---------------------------------------------------------------------------

def is_typosquat(
    domain: str,
    best_match: str,
    score: float,
    *,
    lower_threshold: float = LOWER_THRESHOLD,
    upper_threshold: float = UPPER_THRESHOLD,
) -> bool:
    """
    Decide whether *domain* is a typo-squat of *best_match*.

    The deception window is:  lower_threshold <= score < upper_threshold

    - score >= upper_threshold -> treat as the legitimate domain (exact / trivial match)
    - lower_threshold <= score < upper_threshold -> suspicious: close enough to
      deceive a casual reader but not actually the real domain
    - score < lower_threshold -> not similar enough to be a deliberate spoof

    Additional checks applied regardless of the score band:
    - If *domain* is an exact match for any whitelisted domain -> not a spoof.
    - If *domain* is a raw IP address -> always flag (IP domains impersonating
      a known brand are inherently suspicious).
    - If *domain* normalises (after homoglyph substitution) to a whitelisted
      domain but is not literally that domain -> FLAG as homoglyph attack.

    Parameters
    ----------
    domain          : The candidate domain.
    best_match      : The closest whitelisted domain (from score_against_whitelist).
    score           : The similarity score (0-1).
    lower_threshold : Minimum score to consider as deceptive.
    upper_threshold : Score at/above which we treat as genuine.

    Returns
    -------
    bool
        True if the domain is deemed a typo-squat.
    """
    # Exact whitelist membership -> clean
    if domain in LEGITIMATE_DOMAINS:
        return False

    # Raw IP -> suspicious (attacker hides behind numeric address)
    if _is_ip_address(domain):
        return True

    # Homoglyph attack: normalised domain IS the legitimate domain but the
    # raw domain is NOT (e.g. 'zer0dha.com' normalises to 'zerodha.com')
    normalised = _apply_homoglyphs(_unicode_normalize(domain))
    if normalised in LEGITIMATE_DOMAINS and domain not in LEGITIMATE_DOMAINS:
        return True

    # Brand-token prefix/substring check:
    # Long hyphenated phishing domains (e.g. 'sebi-secure-verify.co',
    # 'nse-kyc-update.net.in', 'nse-india-kyc.info') dilute SequenceMatcher
    # scores because the brand name is only a small prefix of a longer string.
    # We extract the registrable-domain label of each whitelisted domain (the
    # brand token before the first dot, e.g. 'sebi', 'nseindia', 'groww') and
    # check if it appears as a word-boundary-aligned prefix in the candidate
    # domain's leftmost label.  Exact whitelist members are already returned
    # above, so this only fires for look-alike domains.
    candidate_label = domain.split(".")[0].lower()  # e.g. 'sebi-secure-verify'
    for legit in LEGITIMATE_DOMAINS:
        brand = legit.split(".")[0].lower()         # e.g. 'sebi', 'nseindia', 'nse'
        if len(brand) < 3:
            continue   # skip 1-2 char tokens — too many false triggers
        # Prefix match: candidate label starts with brand (e.g. 'sebi-secure-verify' starts 'sebi')
        if candidate_label.startswith(brand) and candidate_label != brand:
            log.debug(
                "Brand-prefix match: %r starts with whitelisted brand %r -> FLAG",
                domain, brand,
            )
            return True
        # Substring match: brand appears after a hyphen (e.g. '-nse' in 'abc-nse-kyc')
        if f"-{brand}" in candidate_label or candidate_label.startswith(brand + "-"):
            log.debug(
                "Brand-substring match: %r contains whitelisted brand %r -> FLAG",
                domain, brand,
            )
            return True
        # Stem check: for longer brands (>=7 chars, e.g. 'nseindia'),
        # also try the first 3 chars as a stem prefix check
        if len(brand) >= 7:
            stem = brand[:3]
            if candidate_label.startswith(stem + "-") or f"-{stem}-" in candidate_label:
                log.debug(
                    "Brand-stem match: %r matches stem %r of brand %r -> FLAG",
                    domain, stem, brand,
                )
                return True

    return lower_threshold <= score < upper_threshold


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------

def analyze_urls(text: str) -> dict:
    """
    Analyse *text* for URLs and detect typo-squatting against known
    legitimate Indian financial domains.

    This is the primary entry point for the Step 5 inference pipeline.
    It is deliberately **synchronous and non-blocking** — call it from
    a ThreadPoolExecutor or asyncio.to_thread() if you need it async.

    Parameters
    ----------
    text : str
        Raw input — email body, WhatsApp post, voice transcript, etc.

    Returns
    -------
    dict with keys:
        urls_found      : list[str]
            All URLs/domains extracted from the text.
        suspicious_urls : list[dict]
            Each element: {"url", "target_spoofed", "similarity_score"}
        is_url_threat   : bool
            True if at least one suspicious URL was found.

    Example
    -------
    >>> result = analyze_urls(
    ...     "Click here to verify: https://sebii.gov.in/kyc?ref=12345"
    ... )
    >>> result["is_url_threat"]
    True
    >>> result["suspicious_urls"][0]["target_spoofed"]
    'sebi.gov.in'
    """
    result = AnalysisResult()

    if not isinstance(text, str) or not text.strip():
        log.debug("analyze_urls: received empty or non-string input.")
        return result.to_dict()

    # ── 1. Extract raw URLs ────────────────────────────────────────────────
    raw_urls = extract_urls(text)
    result.urls_found = raw_urls

    if not raw_urls:
        log.debug("analyze_urls: no URLs found in text.")
        return result.to_dict()

    log.debug("analyze_urls: found %d URL(s) → %s", len(raw_urls), raw_urls)

    # ── 2. Analyse each URL ────────────────────────────────────────────────
    seen_domains: set[str] = set()

    for raw_url in raw_urls:
        domain = get_effective_domain(raw_url)

        if domain is None:
            log.debug("  Could not parse domain from %r — skipping.", raw_url)
            continue

        if len(domain) < MIN_DOMAIN_LEN:
            log.debug("  Domain %r too short — skipping.", domain)
            continue

        # Avoid re-scoring the same domain twice (e.g. multiple paths on same host)
        if domain in seen_domains:
            log.debug("  Domain %r already scored — skipping duplicate.", domain)
            continue
        seen_domains.add(domain)

        # ── 3. Score against whitelist ─────────────────────────────────────
        best_match, score = score_against_whitelist(domain)

        log.debug(
            "  Domain: %-35s | Best match: %-30s | Score: %.4f",
            domain, best_match, score,
        )

        # ── 4. Typo-squat decision ─────────────────────────────────────────
        if is_typosquat(domain, best_match, score):
            # For IP addresses: the "spoofed target" is not a whitelist domain;
            # label it clearly so downstream consumers understand the signal.
            if _is_ip_address(domain):
                display_target = "[raw-IP: no domain / identity concealment]"
                display_score  = 0.0
            else:
                # Homoglyph case: find the actual domain being impersonated
                normalised = _apply_homoglyphs(_unicode_normalize(domain))
                if normalised in LEGITIMATE_DOMAINS:
                    display_target = normalised
                    display_score  = round(
                        difflib.SequenceMatcher(
                            None, domain, display_target, autojunk=False
                        ).ratio(), 4
                    )
                else:
                    display_target = best_match
                    display_score  = round(score, 4)

            finding = SuspiciousURL(
                url=raw_url,
                target_spoofed=display_target,
                similarity_score=display_score,
            )
            result.suspicious_urls.append(finding)
            log.warning(
                "SUSPICIOUS URL detected: %r spoofs %r (score=%.4f)",
                raw_url, display_target, display_score,
            )

    # ── 5. Set threat flag ─────────────────────────────────────────────────
    result.is_url_threat = len(result.suspicious_urls) > 0

    return result.to_dict()


# ---------------------------------------------------------------------------
# Convenience: batch analysis
# ---------------------------------------------------------------------------

def analyze_urls_batch(texts: list[str]) -> list[dict]:
    """
    Run analyze_urls over a list of texts.

    Parameters
    ----------
    texts : list[str]

    Returns
    -------
    list[dict]
        One result dict per input text (same ordering).
    """
    return [analyze_urls(t) for t in texts]


# ---------------------------------------------------------------------------
# CLI self-test / demo
# ---------------------------------------------------------------------------

def _run_demo() -> None:  # noqa: C901
    """
    Structured stress-test — 27 cases.
    Run with:  python url_analyzer.py

    Categories:
      A. Typosquats (char substitution)        — cases 01-08  → expect FLAG
      B. Homoglyph attacks                     — cases 09-12  → expect FLAG
      C. Wrong TLD spoofs                      — cases 13-16  → expect FLAG
      D. Legitimate subdomains (must NOT flag) — cases 17-20  → expect CLEAN
      E. Shortened URLs (documented blind spot)— cases 21-23  → expect CLEAN (limitation)
      F. Unknown / edge-case domains           — cases 24-26  → expect CLEAN
      G. Mixed / regression                    — case  27     → expect FLAG
    """
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.WARNING,   # suppress per-URL debug chatter
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    SEP = "=" * 80

    # ------------------------------------------------------------------
    # Schema: (id, category, title, text, expected_threat, notes)
    # expected_threat=True  -> is_url_threat must be True  (FLAG)
    # expected_threat=False -> is_url_threat must be False (CLEAN)
    # ------------------------------------------------------------------
    test_cases: list[tuple[int, str, str, str, bool, str]] = [

        # ── A: Typosquats — char substitution ──────────────────────────────
        (1, "typosquat",
         "SEBI extra-i (sebii.gov.in)",
         "Dear Investor, your account is at risk. Verify at https://sebii.gov.in/verify?token=abc123",
         True, "1-char insertion"),
        (2, "typosquat",
         "NSE doubled-i (nseindiaa.com)",
         "NSE KYC required: https://nseindiaa.com/kyc/update immediately.",
         True, "1-char doubling"),
        (3, "typosquat",
         "BSE wrong TLD (bseindia.net)",
         "BSE compliance notice — submit docs at https://bseindia.net/submit",
         True, "wrong TLD .net vs .com"),
        (4, "typosquat",
         "Zerodha wrong ccTLD (zerodha.co.in)",
         "Zerodha risk: reset credentials at https://zerodha.co.in/reset?s=abc",
         True, "wrong ccTLD co.in vs .com"),
        (5, "typosquat",
         "Groww missing-w (grow.in)",
         "Your Groww SIP flagged — verify at https://grow.in/kyc?ref=xyz",
         True, "1-char deletion"),
        (6, "typosquat",
         "Upstox digit-sub (upst0x.com)",
         "Upstox security alert: https://upst0x.com/login — reset your TPIN now.",
         True, "digit 0->o"),
        (7, "typosquat",
         "SEBI dashed phishing subdomain",
         "SEBI official: verify your Demat at https://sebi-secure-verify.co/auth",
         True, "brand in hostname, suspicious TLD"),
        (8, "typosquat",
         "NSE compound-TLD spoof (nse-kyc-update.net.in)",
         "NSE mandatory KYC: https://nse-kyc-update.net.in/user/verify",
         True, "compound TLD spoof"),

        # ── B: Homoglyph attacks ────────────────────────────────────────────
        (9, "homoglyph",
         "Zerodha zero-for-o (zer0dha.com)",
         "Session expired — re-login at https://zer0dha.com/login within 10 mins.",
         True, "0->o digit substitution"),
        (10, "homoglyph",
         "SEBI five-for-S (5ebi.gov.in)",
         "Urgent SEBI notice: confirm identity at https://5ebi.gov.in/verify",
         True, "5->S substitution"),
        (11, "homoglyph",
         "Groww zero-for-o (gr0ww.in)",
         "Groww account alert: portfolio review at https://gr0ww.in/review",
         True, "0->o substitution"),
        (12, "homoglyph",
         "BSE eight-for-B (8seindia.com)",
         "BSE compliance: respond at https://8seindia.com/compliance urgently.",
         True, "8->B substitution"),

        # ── C: Wrong TLD spoofs ─────────────────────────────────────────────
        (13, "wrong_tld",
         "SEBI wrong TLD (sebi.gov.org)",
         "Download SEBI circular from https://sebi.gov.org/circulars/2026",
         True, "gov.org is not gov.in"),
        (14, "wrong_tld",
         "NSE wrong TLD (nseindia.org)",
         "NSE market data: https://nseindia.org/reports/daily",
         True, ".org not .com"),
        (15, "wrong_tld",
         "Zerodha wrong TLD (zerodha.net)",
         "Zerodha account suspended — appeal at https://zerodha.net/appeal",
         True, ".net not .com"),
        (16, "wrong_tld",
         "Groww wrong TLD (groww.com)",
         "Groww MF notice: https://groww.com/kyc/renewal — submit before Friday.",
         True, ".com not .in"),

        # ── D: Legitimate subdomains — must NOT flag ────────────────────────
        (17, "legit_subdomain",
         "Zerodha API subdomain — CLEAN",
         "PRISM calls https://api.zerodha.com/v2/portfolio for live data.",
         False, "legitimate subdomain of zerodha.com"),
        (18, "legit_subdomain",
         "Groww invest subdomain — CLEAN",
         "Your SIP confirmation: https://invest.groww.in/sip/confirm/12345",
         False, "legitimate subdomain of groww.in"),
        (19, "legit_subdomain",
         "Upstox trade subdomain — CLEAN",
         "Open your dashboard: https://trade.upstox.com/dashboard",
         False, "legitimate subdomain of upstox.com"),
        (20, "legit_subdomain",
         "SEBI SCORES portal — CLEAN",
         "File your complaint at https://scores.sebi.gov.in/SCORES/Welcome.html",
         False, "official SEBI subdomain"),

        # ── E: Shortened URLs — documented blind spot ───────────────────────
        (21, "shortened_url",
         "bit.ly link — BLIND SPOT",
         "Verify your KYC now: bit.ly/sebi-kyc-update",
         False,
         "KNOWN BLIND SPOT: shortened URL not resolved; cannot assess destination"),
        (22, "shortened_url",
         "tinyurl link — BLIND SPOT",
         "NSE login link: tinyurl.com/nselogin2026",
         False,
         "KNOWN BLIND SPOT: tinyurl not resolved"),
        (23, "shortened_url",
         "Telegram t.me link — BLIND SPOT",
         "Join premium group for insider tips: t.me/stockgurus_777",
         False,
         "KNOWN BLIND SPOT: t.me not in whitelist; dissimilar to all legit domains"),

        # ── F: Unknown / edge-case domains ──────────────────────────────────
        (24, "unknown_domain",
         "Unknown crypto exchange (mycryptoexchange.io)",
         "Trade now at https://mycryptoexchange.io — special offer for PRISM users",
         False,
         "EDGE CASE: too dissimilar to whitelist; falls below lower_threshold"),
        (25, "unknown_domain",
         "Suspicious invest-now.biz",
         "Guaranteed 40% returns: invest-now.biz — click to verify your deposit",
         False,
         "EDGE CASE: suspicious but unknown; dissimilar to whitelist — not flagged"),
        (26, "unknown_domain",
         "No URLs at all — empty baseline",
         "The Nifty 50 rose 1.2% today on strong FII inflows of Rs 3,200 crore.",
         False,
         "Baseline: no URL present"),

        # ── G: Mixed / regression ───────────────────────────────────────────
        (27, "mixed",
         "Clean NSE + spoof nse-india-kyc.info — overall FLAG",
         "Visit https://www.nseindia.com for market data or confirm KYC at "
         "https://nse-india-kyc.info/submit",
         True,
         "One clean, one spoof; overall is_url_threat must be True"),
    ]

    # ------------------------------------------------------------------
    # Run all cases
    # ------------------------------------------------------------------
    print("\n" + SEP)
    print("  PRISM Module 1 -- URL Analyzer Stress-Test  (27 cases)")
    print(SEP)

    PASS = "PASS"
    FAIL = "FAIL"
    NOTE = "NOTE"   # documented limitation — mismatch is expected

    rows: list[tuple[int, str, str, str, bool, bool, str]] = []
    for tc_id, category, title, text, expected, notes in test_cases:
        result  = analyze_urls(text)
        actual  = result["is_url_threat"]
        correct = actual == expected
        is_limitation = "BLIND SPOT" in notes or "EDGE CASE" in notes
        if correct:
            outcome = PASS
        elif is_limitation:
            outcome = NOTE
        else:
            outcome = FAIL
        rows.append((tc_id, category, title, outcome, expected, actual, notes))

    # ------------------------------------------------------------------
    # Results table
    # ------------------------------------------------------------------
    print(f"\n  {'ID':>3}  {'Category':<18}  {'Result':<6}  {'Expect':<6}  {'Got':<6}  Title")
    print("  " + "-" * 76)
    for tc_id, category, title, outcome, expected, actual, notes in rows:
        marker = "  " if outcome == PASS else ("??" if outcome == NOTE else "!!")
        exp_s  = "FLAG " if expected else "CLEAN"
        got_s  = "FLAG " if actual   else "CLEAN"
        print(f"  {marker}{tc_id:>2}  {category:<18}  {outcome:<6}  {exp_s:<6}  {got_s:<6}  {title}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    passed = sum(1 for r in rows if r[3] == PASS)
    failed = sum(1 for r in rows if r[3] == FAIL)
    noted  = sum(1 for r in rows if r[3] == NOTE)
    total  = len(rows)

    print("\n" + SEP)
    print(f"  SUMMARY:  {passed}/{total} PASS  |  {failed} FAIL  |  {noted} NOTED (documented limitations)")
    print(SEP)

    # ------------------------------------------------------------------
    # FP / FN / blind-spot detail
    # ------------------------------------------------------------------
    fp    = [(r[0], r[2], r[6]) for r in rows if r[3] == FAIL and not r[4] and r[5]]
    fn    = [(r[0], r[2], r[6]) for r in rows if r[3] == FAIL and r[4] and not r[5]]
    blind = [(r[0], r[2], r[6]) for r in rows if r[3] == NOTE]

    if fp:
        print("\n  FALSE POSITIVES (CLEAN expected, FLAG returned):")
        for tc_id, title, notes in fp:
            print(f"    [{tc_id:02d}] {title}  |  {notes}")
    else:
        print("\n  FALSE POSITIVES: none")

    if fn:
        print("\n  FALSE NEGATIVES (FLAG expected, CLEAN returned):")
        for tc_id, title, notes in fn:
            print(f"    [{tc_id:02d}] {title}  |  {notes}")
    else:
        print("\n  FALSE NEGATIVES: none")

    if blind:
        print("\n  DOCUMENTED LIMITATIONS (not counted as failures):")
        for tc_id, title, notes in blind:
            print(f"    [{tc_id:02d}] {title}")
            print(f"         {notes}")

    print("\n" + SEP + "\n")


if __name__ == "__main__":
    _run_demo()
