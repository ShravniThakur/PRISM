import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./prism_auth.db")

        # Text: TLSH distance between normalized texts (0 = identical).
        # Measured on ~400-char advisories: real forwards ("Fwd:" prefix,
        # trailing notes) score 80-95, meaning rewrites 180+, unrelated text
        # 250+. Single-token swaps (a changed URL) score under 20, which is
        # why text matching also requires the critical-token check.
        self.text_tlsh_max_diff = int(os.getenv("TEXT_TLSH_MAX_DIFF", "100"))

        # Image: Hamming distance between 64-bit pHashes. Recompression stays
        # within a few bits; visual edits jump far beyond this.
        self.image_phash_max_hamming = int(os.getenv("IMAGE_PHASH_MAX_HAMMING", "10"))

        # Video: per-frame pHash Hamming threshold, and the share of signed
        # frames that must find a match in the uploaded copy.
        self.video_frame_max_hamming = int(os.getenv("VIDEO_FRAME_MAX_HAMMING", "12"))
        self.video_min_match_ratio = float(os.getenv("VIDEO_MIN_MATCH_RATIO", "0.9"))
        self.video_sample_fps = float(os.getenv("VIDEO_SAMPLE_FPS", "1.0"))


settings = Settings()
