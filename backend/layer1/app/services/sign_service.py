import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..crypto import signing
from ..models import Entity, SignedAsset
from . import payload as payload_mod
from . import registry


def prepare(media_type: str, algorithm: str, hashes: list[str]) -> dict:
    payload = payload_mod.build_payload(media_type, algorithm, hashes)
    return {"payload": payload, "payload_b64": payload_mod.encode_payload(payload)}


def submit(
    db: Session,
    entity_id: str,
    payload_b64: str,
    signature_b64: str,
    title: str | None = None,
    reference_url: str | None = None,
) -> SignedAsset:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")

    try:
        payload, raw = payload_mod.decode_payload(payload_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed payload_b64")

    key = registry.active_key(db, entity_id)
    if key is None:
        raise HTTPException(status_code=409, detail="entity has no active key")
    if not signing.verify(key.public_key_pem, raw, signature_b64):
        raise HTTPException(
            status_code=400,
            detail="signature does not verify against the entity's active public key",
        )

    asset = SignedAsset(
        entity_id=entity_id,
        media_type=payload["media_type"],
        algorithm=payload["algorithm"],
        hashes=json.dumps(payload["hashes"]),
        payload=raw.decode(),
        signature=signature_b64,
        title=title,
        reference_url=reference_url,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
