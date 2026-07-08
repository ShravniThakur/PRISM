from datetime import datetime

from sqlalchemy.orm import Session

from ..crypto import keys as crypto_keys
from ..models import Entity, KeyPair, utcnow


def create_entity(
    db: Session,
    name: str,
    entity_type: str,
    public_key_pem: str | None = None,
) -> tuple[Entity, str | None]:
    """Registers an entity. If no public key is supplied, generates a keypair
    and returns the private key PEM — the only time it ever exists server-side.
    Returns (entity, private_key_pem_or_None)."""
    entity = Entity(name=name, type=entity_type)
    db.add(entity)
    db.flush()

    private_pem = None
    if public_key_pem:
        crypto_keys.load_public_key(public_key_pem)  # validate
    else:
        private_pem, public_key_pem = crypto_keys.generate_keypair()
    db.add(KeyPair(entity_id=entity.id, public_key_pem=public_key_pem))
    db.commit()
    db.refresh(entity)
    return entity, private_pem


def rotate_key(db: Session, entity: Entity) -> tuple[KeyPair, str]:
    """Revokes all active keys and issues a fresh keypair.
    Returns (new_key, private_key_pem)."""
    now = utcnow()
    for key in entity.keys:
        if key.revoked_at is None:
            key.revoked_at = now
    private_pem, public_pem = crypto_keys.generate_keypair()
    new_key = KeyPair(entity_id=entity.id, public_key_pem=public_pem)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return new_key, private_pem


def active_key(db: Session, entity_id: str) -> KeyPair | None:
    return (
        db.query(KeyPair)
        .filter(KeyPair.entity_id == entity_id, KeyPair.revoked_at.is_(None))
        .order_by(KeyPair.created_at.desc())
        .first()
    )


def keys_valid_at(db: Session, entity_id: str, at: datetime) -> list[KeyPair]:
    """Keys that were valid at a point in time — lets assets signed before a
    rotation keep verifying."""
    return (
        db.query(KeyPair)
        .filter(
            KeyPair.entity_id == entity_id,
            KeyPair.created_at <= at,
            (KeyPair.revoked_at.is_(None)) | (KeyPair.revoked_at >= at),
        )
        .all()
    )
