import base64
import json

# Bump when hashing/normalization changes so old signatures stay verifiable
# under the version they were created with.
PAYLOAD_VERSION = 1

MEDIA_TYPES = {"text", "image", "video", "audio"}


def build_payload(media_type: str, algorithm: str, hashes: list[str]) -> dict:
    return {
        "version": PAYLOAD_VERSION,
        "media_type": media_type,
        "algorithm": algorithm,
        "hashes": hashes,
    }


def canonical_bytes(payload: dict) -> bytes:
    """Deterministic serialization — these exact bytes are what gets signed."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def encode_payload(payload: dict) -> str:
    return base64.b64encode(canonical_bytes(payload)).decode()


def decode_payload(payload_b64: str) -> tuple[dict, bytes]:
    raw = base64.b64decode(payload_b64)
    payload = json.loads(raw)
    if (
        not isinstance(payload, dict)
        or payload.get("media_type") not in MEDIA_TYPES
        or not isinstance(payload.get("algorithm"), str)
        or not isinstance(payload.get("hashes"), list)
        or not payload["hashes"]
        or not all(isinstance(h, str) for h in payload["hashes"])
    ):
        raise ValueError("malformed payload")
    return payload, raw
