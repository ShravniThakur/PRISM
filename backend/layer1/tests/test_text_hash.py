from app.hashing import text_hash

ADVISORY = (
    "SEBI Investor Advisory: SEBI has observed fraudulent trading platforms "
    "impersonating registered brokers and promising guaranteed returns. "
    "Investors are advised to transact only through SEBI-registered "
    "intermediaries and to verify registration numbers on the official SEBI "
    "website www.sebi.gov.in before investing."
)

# Same message after a WhatsApp forward: emoji, casing, whitespace noise.
FORWARDED = (
    "🚨🚨 SEBI INVESTOR ADVISORY:   SEBI has observed fraudulent trading "
    "platforms impersonating registered brokers and promising GUARANTEED "
    "returns!! Investors are advised to transact only through "
    "SEBI-registered intermediaries and to verify registration numbers on "
    "the official SEBI website www.sebi.gov.in before investing... 🚨"
)

# A forward with real edits: prefix and trailing note added.
FORWARDED_WITH_EDITS = (
    "Fwd: " + ADVISORY + " Please share this with family and friends."
)

SCAM = (
    "URGENT from SEBI: your demat account will be suspended today. To keep "
    "your holdings safe, immediately transfer your funds to the secure "
    "escrow account 004512890 at the link below and share the OTP with our "
    "verification officer to confirm your identity."
)


def test_forward_noise_normalizes_identically():
    assert text_hash.normalize_text(ADVISORY) == text_hash.normalize_text(FORWARDED)


def test_long_text_uses_tlsh():
    algorithm, hashes = text_hash.compute(ADVISORY)
    assert algorithm == "tlsh"
    assert not hashes[0].startswith("tok:")
    assert "tok:www.sebi.gov.in" in hashes[1:]


def test_short_text_falls_back_to_sha256():
    algorithm, _ = text_hash.compute("hi")
    assert algorithm == "sha256"


def test_forwarded_copy_matches():
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(FORWARDED)
    similarity, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert matched
    assert similarity == 1.0


def test_forward_with_real_edits_still_matches():
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(FORWARDED_WITH_EDITS)
    _, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert matched


def test_different_meaning_does_not_match():
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(SCAM)
    _, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert not matched


def test_extract_critical_tokens():
    tokens = text_hash.extract_critical_tokens(
        "Visit www.sebi.gov.in or https://nse-india.com/kyc and pay to "
        "account 0045-1289-0033 before 2026."
    )
    assert "www.sebi.gov.in" in tokens
    assert "https://nse-india.com/kyc" in tokens
    assert "004512890033" in tokens
    assert "2026" not in tokens  # short digit runs (years, dates) ignored


def test_url_swap_attack_does_not_match():
    # TLSH distance for a single swapped URL is tiny — the token check
    # must catch it.
    attack = ADVISORY.replace("www.sebi.gov.in", "www.sebi-kyc-verify.in")
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(attack)
    similarity, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert similarity > 0.9  # fuzzy hash alone would have let this through
    assert not matched


def test_inserted_account_number_does_not_match():
    attack = ADVISORY + " For refunds transfer to account 004512890 today."
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(attack)
    _, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert not matched


def test_truncated_forward_missing_a_token_still_matches():
    truncated = ADVISORY.replace(" www.sebi.gov.in", "")
    alg_a, hashes_a = text_hash.compute(ADVISORY)
    alg_b, hashes_b = text_hash.compute(truncated)
    _, matched = text_hash.compare(alg_a, hashes_a, alg_b, hashes_b)
    assert matched
