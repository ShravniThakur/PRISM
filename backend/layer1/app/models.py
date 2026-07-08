import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    # Naive UTC everywhere: SQLite returns naive datetimes, and mixing
    # aware/naive values breaks comparisons.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False, unique=True, index=True)
    type = Column(String, nullable=False, default="broker")  # regulator/exchange/broker
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    keys = relationship("KeyPair", back_populates="entity", order_by="KeyPair.created_at")
    signed_assets = relationship("SignedAsset", back_populates="entity")


class KeyPair(Base):
    """A public key registered for an entity. Private keys are never stored."""

    __tablename__ = "key_pairs"

    id = Column(String, primary_key=True, default=new_id)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)
    public_key_pem = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    revoked_at = Column(DateTime, nullable=True)

    entity = relationship("Entity", back_populates="keys")


class SignedAsset(Base):
    """A fuzzy hash of an official asset, signed by the entity's private key."""

    __tablename__ = "signed_assets"

    id = Column(String, primary_key=True, default=new_id)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)
    media_type = Column(String, nullable=False, index=True)  # text/image/video
    algorithm = Column(String, nullable=False)  # tlsh/sha256/phash/phash-seq
    hashes = Column(Text, nullable=False)  # JSON list of hash strings
    payload = Column(Text, nullable=False)  # canonical JSON that was signed
    signature = Column(Text, nullable=False)  # base64 Ed25519 signature of payload
    title = Column(String, nullable=True)
    reference_url = Column(String, nullable=True)
    signed_at = Column(DateTime, nullable=False, default=utcnow)

    entity = relationship("Entity", back_populates="signed_assets")
