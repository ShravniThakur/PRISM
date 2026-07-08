import hashlib
import re
import unicodedata

import tlsh

from ..config import settings

# TLSH needs at least ~50 bytes with enough variation; below that we fall
# back to an exact hash of the normalized text.
_MIN_TLSH_BYTES = 50

# Critical tokens (URLs, account/phone-length numbers) travel alongside the
# fuzzy hash in the hashes list, prefixed so compare() can split them out.
# TLSH barely moves when a scammer swaps a single URL or inserts an account
# number into otherwise-genuine text, so these are checked exactly.
_TOKEN_PREFIX = "tok:"
_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\b[a-z0-9][a-z0-9.-]*\.(?:com|net|org|in|io|co|gov|info|biz|me|app|xyz)(?:/\S*)?"
)
_NUMBER_RE = re.compile(r"\d(?:[\d\-\s]{4,})\d")
_MIN_TOKEN_DIGITS = 6


def normalize_text(text: str) -> str:
    """Strip forwarding noise (casing, emoji, punctuation, whitespace runs)
    so a WhatsApp forward of the same message normalizes identically."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_critical_tokens(text: str) -> list[str]:
    """URLs and long digit runs from the raw text (before normalization,
    which would strip the dots out of domains)."""
    tokens: set[str] = set()
    for match in _URL_RE.findall(unicodedata.normalize("NFKC", text).lower()):
        tokens.add(match.rstrip(".,;:!?)(\"'"))
    for match in _NUMBER_RE.findall(text):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= _MIN_TOKEN_DIGITS:
            tokens.add(digits)
    return sorted(tokens)


def compute(text: str) -> tuple[str, list[str]]:
    """Returns (algorithm, hashes). hashes[0] is the fuzzy/exact digest;
    the rest are critical-token entries."""
    tokens = [_TOKEN_PREFIX + t for t in extract_critical_tokens(text)]
    data = normalize_text(text).encode()
    digest = ""
    if len(data) >= _MIN_TLSH_BYTES:
        digest = tlsh.hash(data)
    if not digest or digest == "TNULL":
        return "sha256", [hashlib.sha256(data).hexdigest()] + tokens
    return "tlsh", [digest] + tokens


def _split(hashes: list[str]) -> tuple[str, set[str]]:
    return hashes[0], {h for h in hashes[1:] if h.startswith(_TOKEN_PREFIX)}


def compare(
    stored_algorithm: str,
    stored_hashes: list[str],
    algorithm: str,
    hashes: list[str],
) -> tuple[float, bool]:
    """Returns (similarity in [0,1], matched). Matching requires both the
    fuzzy distance to be under threshold AND no critical token in the upload
    that wasn't in the signed original (a truncated forward may drop tokens;
    it may never introduce or alter one)."""
    if stored_algorithm != algorithm:
        return 0.0, False
    stored_digest, stored_tokens = _split(stored_hashes)
    digest, tokens = _split(hashes)
    tokens_ok = tokens <= stored_tokens

    if algorithm == "sha256":
        same = stored_digest == digest
        return (1.0, tokens_ok) if same else (0.0, False)

    diff = tlsh.diff(stored_digest, digest)
    similarity = max(0.0, 1.0 - diff / 300.0)
    return similarity, tokens_ok and diff <= settings.text_tlsh_max_diff
