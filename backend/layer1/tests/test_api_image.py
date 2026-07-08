import base64
import io
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.crypto import signing
from app.main import app

client = TestClient(app)


def make_announcement_image() -> Image.Image:
    """A structured image standing in for an official announcement graphic."""
    gradient = np.zeros((256, 256, 3), dtype=np.uint8)
    gradient[..., 0] = np.linspace(20, 200, 256)[None, :]
    gradient[..., 1] = np.linspace(40, 160, 256)[:, None]
    gradient[..., 2] = 90
    image = Image.fromarray(gradient)
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 60, 196, 196), fill=(240, 240, 240))
    draw.rectangle((20, 200, 236, 240), fill=(10, 10, 40))
    draw.line((0, 128, 256, 128), fill=(255, 200, 0), width=4)
    return image


def encode(image: Image.Image, fmt: str, **kwargs) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


@pytest.fixture
def entity():
    response = client.post(
        "/entities",
        json={"name": f"NSE-{uuid.uuid4().hex[:8]}", "type": "exchange"},
    )
    assert response.status_code == 201
    return response.json()


def sign_image(entity: dict, data: bytes, filename: str = "official.png") -> None:
    prepared = client.post(
        "/sign/prepare", files={"file": (filename, data, "image/png")}
    ).json()
    signature = signing.sign(
        entity["private_key_pem"], base64.b64decode(prepared["payload_b64"])
    )
    response = client.post(
        "/sign/submit",
        json={
            "entity_id": entity["id"],
            "payload_b64": prepared["payload_b64"],
            "signature_b64": signature,
            "title": "official graphic",
        },
    )
    assert response.status_code == 201, response.text


def test_recompressed_copy_authenticates(entity):
    original = make_announcement_image()
    sign_image(entity, encode(original, "PNG"))

    # Simulate a WhatsApp forward: heavy JPEG recompression + slight resize.
    degraded = original.resize((230, 230)).resize((256, 256))
    result = client.post(
        "/verify",
        files={"file": ("forward.jpg", encode(degraded, "JPEG", quality=35), "image/jpeg")},
    ).json()
    assert result["is_authenticated_sender"] == 1
    assert result["matched_entity"] == entity["name"]


def test_visually_edited_copy_fails(entity):
    original = make_announcement_image()
    sign_image(entity, encode(original, "PNG"))

    tampered = original.copy()
    draw = ImageDraw.Draw(tampered)
    draw.rectangle((0, 100, 256, 256), fill=(255, 0, 0))  # overwrite the content
    result = client.post(
        "/verify",
        files={"file": ("tampered.png", encode(tampered, "PNG"), "image/png")},
    ).json()
    assert result["is_authenticated_sender"] == 0
