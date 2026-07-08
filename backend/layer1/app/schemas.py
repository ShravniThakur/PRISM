from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KeyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    public_key_pem: str
    created_at: datetime
    revoked_at: datetime | None = None


class EntityCreate(BaseModel):
    name: str
    type: str = "broker"
    # Bring-your-own public key; if omitted a keypair is generated and the
    # private key is returned once in the response.
    public_key_pem: str | None = None


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    keys: list[KeyInfo] = []


class EntityCreated(EntityOut):
    private_key_pem: str | None = None


class RotateOut(BaseModel):
    entity_id: str
    key_id: str
    public_key_pem: str
    private_key_pem: str


class PrepareOut(BaseModel):
    payload: dict
    payload_b64: str


class SignSubmit(BaseModel):
    entity_id: str
    payload_b64: str
    signature_b64: str
    title: str | None = None
    reference_url: str | None = None


class SignedAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    media_type: str
    algorithm: str
    title: str | None = None
    reference_url: str | None = None
    signed_at: datetime


class VerifyOut(BaseModel):
    is_authenticated_sender: int
    media_type: str
    algorithm: str
    similarity: float
    signature_valid: bool | None = None
    matched_entity: str | None = None
    matched_entity_id: str | None = None
    signed_asset_id: str | None = None
    detail: str
