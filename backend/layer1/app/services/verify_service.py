import json

from sqlalchemy.orm import Session

from ..crypto import signing
from ..hashing import image_hash, text_hash, video_hash, audio_hash
from ..models import SignedAsset
from . import registry

_COMPARATORS = {
    "text": text_hash.compare,
    "image": image_hash.compare,
    "video": video_hash.compare,
    "audio": audio_hash.compare,
}


def verify(db: Session, media_type: str, algorithm: str, hashes: list[str]) -> dict:
    """The two-check flow: find the closest signed original by fuzzy-hash
    similarity, then verify its stored signature against a key that was valid
    when it was signed."""
    compare = _COMPARATORS[media_type]
    candidates = (
        db.query(SignedAsset).filter(SignedAsset.media_type == media_type).all()
    )

    best_asset: SignedAsset | None = None
    best_asset_similarity = 0.0
    best_similarity = 0.0
    for asset in candidates:
        similarity, matched = compare(
            asset.algorithm, json.loads(asset.hashes), algorithm, hashes
        )
        best_similarity = max(best_similarity, similarity)
        if matched and similarity >= best_asset_similarity:
            best_asset = asset
            best_asset_similarity = similarity

    if best_asset is None:
        if best_similarity >= 0.85:
            # Nearly identical to a signed original yet failed to match:
            # classic tampering (swapped URL, inserted account number, spliced
            # segment). Worth surfacing loudly in the verdict panel.
            detail = (
                "TAMPERING SUSPECTED: this closely resembles a signed official "
                "communication, but critical details (links, numbers, or "
                "content) differ from the original."
            )
        else:
            detail = (
                "No signed original found in the registry. Unauthenticated "
                "does not mean malicious — Layer 2 decides that."
            )
        return {
            "is_authenticated_sender": 0,
            "media_type": media_type,
            "algorithm": algorithm,
            "similarity": round(best_similarity, 4),
            "signature_valid": None,
            "matched_entity": None,
            "matched_entity_id": None,
            "signed_asset_id": None,
            "detail": detail,
        }

    valid_keys = registry.keys_valid_at(db, best_asset.entity_id, best_asset.signed_at)
    payload_bytes = best_asset.payload.encode()
    signature_valid = any(
        signing.verify(key.public_key_pem, payload_bytes, best_asset.signature)
        for key in valid_keys
    )

    authenticated = signature_valid
    if signature_valid:
        detail = (
            f"Matches '{best_asset.title or best_asset.id}' signed by "
            f"{best_asset.entity.name} on {best_asset.signed_at.date().isoformat()}"
        )
    else:
        detail = (
            "A similar signed record exists but its signature does not verify — "
            "treat as unauthenticated"
        )

    return {
        "is_authenticated_sender": 1 if authenticated else 0,
        "media_type": media_type,
        "algorithm": algorithm,
        "similarity": round(best_asset_similarity, 4),
        "signature_valid": signature_valid,
        "matched_entity": best_asset.entity.name if authenticated else None,
        "matched_entity_id": best_asset.entity_id if authenticated else None,
        "signed_asset_id": best_asset.id if authenticated else None,
        "detail": detail,
    }
