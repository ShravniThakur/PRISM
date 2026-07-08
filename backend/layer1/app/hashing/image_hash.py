import io

import imagehash
from PIL import Image

from ..config import settings


def compute(data: bytes) -> tuple[str, list[str]]:
    """Returns (algorithm, hashes) for an image file's bytes."""
    image = Image.open(io.BytesIO(data)).convert("RGB")
    return "phash", [str(imagehash.phash(image))]


def compare(
    stored_algorithm: str,
    stored_hashes: list[str],
    algorithm: str,
    hashes: list[str],
) -> tuple[float, bool]:
    if stored_algorithm != algorithm or algorithm != "phash":
        return 0.0, False
    distance = imagehash.hex_to_hash(stored_hashes[0]) - imagehash.hex_to_hash(hashes[0])
    similarity = max(0.0, 1.0 - distance / 64.0)
    return similarity, distance <= settings.image_phash_max_hamming
