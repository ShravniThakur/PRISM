import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from app.crypto import signing
from app.main import app

client = TestClient(app)

ADVISORY = (
    "SEBI Investor Advisory: SEBI has observed fraudulent trading platforms "
    "impersonating registered brokers and promising guaranteed returns. "
    "Investors are advised to transact only through SEBI-registered "
    "intermediaries and to verify registration numbers on the official SEBI "
    "website before investing."
)

FORWARDED = (
    "🚨 SEBI INVESTOR ADVISORY:  SEBI has observed fraudulent trading "
    "platforms impersonating registered brokers and promising GUARANTEED "
    "returns!! Investors are advised to transact only through "
    "SEBI-registered intermediaries and to verify registration numbers on "
    "the official SEBI website before investing."
)

SCAM = (
    "URGENT from SEBI: your demat account will be suspended today. To keep "
    "your holdings safe, immediately transfer your funds to the secure "
    "escrow account 004512890 at the link below and share the OTP with our "
    "verification officer to confirm your identity."
)


@pytest.fixture
def entity():
    response = client.post(
        "/entities",
        json={"name": f"SEBI-{uuid.uuid4().hex[:8]}", "type": "regulator"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["private_key_pem"]
    return body


def sign_text(entity: dict, text: str, title: str = "advisory") -> dict:
    prepared = client.post("/sign/prepare", data={"text": text}).json()
    signature = signing.sign(
        entity["private_key_pem"], base64.b64decode(prepared["payload_b64"])
    )
    response = client.post(
        "/sign/submit",
        json={
            "entity_id": entity["id"],
            "payload_b64": prepared["payload_b64"],
            "signature_b64": signature,
            "title": title,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_forwarded_copy_authenticates(entity):
    sign_text(entity, ADVISORY)
    result = client.post("/verify", data={"text": FORWARDED}).json()
    assert result["is_authenticated_sender"] == 1
    assert result["signature_valid"] is True
    assert result["matched_entity"] == entity["name"]
    assert result["similarity"] >= 0.8


def test_scam_text_does_not_authenticate(entity):
    sign_text(entity, ADVISORY)
    result = client.post("/verify", data={"text": SCAM}).json()
    assert result["is_authenticated_sender"] == 0


def test_submit_with_wrong_key_rejected(entity):
    other = client.post(
        "/entities",
        json={"name": f"FAKE-{uuid.uuid4().hex[:8]}", "type": "broker"},
    ).json()
    prepared = client.post("/sign/prepare", data={"text": ADVISORY}).json()
    forged = signing.sign(
        other["private_key_pem"], base64.b64decode(prepared["payload_b64"])
    )
    response = client.post(
        "/sign/submit",
        json={
            "entity_id": entity["id"],
            "payload_b64": prepared["payload_b64"],
            "signature_b64": forged,
        },
    )
    assert response.status_code == 400


def test_assets_survive_key_rotation(entity):
    sign_text(entity, ADVISORY)
    rotation = client.post(f"/entities/{entity['id']}/keys/rotate")
    assert rotation.status_code == 200

    # Asset signed before rotation still verifies against the historical key.
    result = client.post("/verify", data={"text": ADVISORY}).json()
    assert result["is_authenticated_sender"] == 1

    # The old private key can no longer submit new assets.
    prepared = client.post("/sign/prepare", data={"text": SCAM}).json()
    stale_signature = signing.sign(
        entity["private_key_pem"], base64.b64decode(prepared["payload_b64"])
    )
    response = client.post(
        "/sign/submit",
        json={
            "entity_id": entity["id"],
            "payload_b64": prepared["payload_b64"],
            "signature_b64": stale_signature,
        },
    )
    assert response.status_code == 400


def test_verify_with_no_input_rejected():
    assert client.post("/verify", data={}).status_code == 400


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
