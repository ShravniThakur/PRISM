import hashlib

def compute(data: bytes, suffix: str = ".mp3") -> tuple[str, list[str]]:
    """Returns (algorithm, hashes). For audio, we use exact cryptographic SHA-256
    since audio files do not have robust fuzzy visual frames."""
    digest = hashlib.sha256(data).hexdigest()
    return "sha256-audio", [digest]

def compare(
    stored_algorithm: str,
    stored_hashes: list[str],
    algorithm: str,
    hashes: list[str],
) -> tuple[float, bool]:
    """Exact comparison for audio SHA-256."""
    if stored_algorithm != algorithm or algorithm != "sha256-audio":
        return 0.0, False
    if not stored_hashes or not hashes:
        return 0.0, False
        
    same = (stored_hashes[0] == hashes[0])
    return (1.0, same) if same else (0.0, False)
