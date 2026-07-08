import pathlib

import cv2
import numpy as np
import pytest

from app.hashing import video_hash


def write_video(path: pathlib.Path, tampered_after: int | None = None) -> None:
    """3s synthetic clip: textured background + moving bright square. If
    tampered_after is set, the scene is replaced from that frame on (a splice)."""
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24, (128, 128)
    )
    assert writer.isOpened()
    rng = np.random.default_rng(7)
    background = rng.integers(0, 120, (128, 128, 3), dtype=np.uint8)
    spliced_background = rng.integers(120, 255, (128, 128, 3), dtype=np.uint8)
    for i in range(72):
        if tampered_after is not None and i >= tampered_after:
            frame = spliced_background.copy()
            cv2.circle(frame, (64, 64), 30, (0, 0, 255), -1)
        else:
            frame = background.copy()
            x = 10 + i
            cv2.rectangle(frame, (x, 40), (x + 24, 88), (255, 255, 0), -1)
        writer.write(frame)
    writer.release()


@pytest.fixture
def original(tmp_path):
    path = tmp_path / "original.mp4"
    write_video(path)
    return path


def test_same_file_matches(original):
    algorithm, hashes = video_hash.compute(original.read_bytes())
    assert algorithm == "phash-seq"
    assert len(hashes) >= 2
    similarity, matched = video_hash.compare(algorithm, hashes, algorithm, hashes)
    assert matched
    assert similarity == 1.0


def test_spliced_video_fails(original, tmp_path):
    tampered_path = tmp_path / "tampered.mp4"
    write_video(tampered_path, tampered_after=24)  # last 2 of 3 seconds replaced

    _, original_hashes = video_hash.compute(original.read_bytes())
    _, tampered_hashes = video_hash.compute(tampered_path.read_bytes())
    _, matched = video_hash.compare(
        "phash-seq", original_hashes, "phash-seq", tampered_hashes
    )
    assert not matched


def test_unrelated_video_fails(original, tmp_path):
    other_path = tmp_path / "other.mp4"
    write_video(other_path, tampered_after=0)

    _, original_hashes = video_hash.compute(original.read_bytes())
    _, other_hashes = video_hash.compute(other_path.read_bytes())
    similarity, matched = video_hash.compare(
        "phash-seq", original_hashes, "phash-seq", other_hashes
    )
    assert not matched
