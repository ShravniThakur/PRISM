import os
import tempfile

import cv2
import imagehash
from PIL import Image

from ..config import settings


def compute(data: bytes, suffix: str = ".mp4") -> tuple[str, list[str]]:
    """Returns (algorithm, hashes): one pHash per sampled frame.

    OpenCV can only decode from a path, so the upload is spooled to a
    temp file for the duration of the call.
    """
    fd, path = tempfile.mkstemp(suffix=suffix or ".mp4")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return "phash-seq", _hash_frames(path)
    finally:
        os.unlink(path)


def _hash_frames(path: str) -> list[str]:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError("could not decode video")
    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    step = max(1, round(fps / settings.video_sample_fps)) if fps > 0 else 30
    hashes: list[str] = []
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % step == 0:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            hashes.append(str(imagehash.phash(image)))
        index += 1
    capture.release()
    if not hashes:
        raise ValueError("no frames could be extracted from video")
    return hashes


def compare(
    stored_algorithm: str,
    stored_hashes: list[str],
    algorithm: str,
    hashes: list[str],
) -> tuple[float, bool]:
    """Aligns the two frame sequences by relative position and counts signed
    frames that find a close match nearby. A spliced/replaced segment fails a
    contiguous run of frames and drags the ratio under the threshold."""
    if stored_algorithm != algorithm or algorithm != "phash-seq":
        return 0.0, False
    if not stored_hashes or not hashes:
        return 0.0, False
    matched = 0
    for i, stored_hex in enumerate(stored_hashes):
        center = round(i * len(hashes) / len(stored_hashes))
        start = max(0, min(center - 2, len(hashes) - 1))
        stop = min(len(hashes), center + 3)
        if stop <= start:
            stop = start + 1
        stored_hash = imagehash.hex_to_hash(stored_hex)
        best = min(
            stored_hash - imagehash.hex_to_hash(hashes[j]) for j in range(start, stop)
        )
        if best <= settings.video_frame_max_hamming:
            matched += 1
    ratio = matched / len(stored_hashes)
    return ratio, ratio >= settings.video_min_match_ratio
