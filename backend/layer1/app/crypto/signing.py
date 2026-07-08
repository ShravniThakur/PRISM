import base64

from cryptography.exceptions import InvalidSignature

from .keys import load_private_key, load_public_key


def sign(private_key_pem: str, message: bytes) -> str:
    """Sign message bytes, returning a base64 signature."""
    signature = load_private_key(private_key_pem).sign(message)
    return base64.b64encode(signature).decode()


def verify(public_key_pem: str, message: bytes, signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
        load_public_key(public_key_pem).verify(signature, message)
        return True
    except (InvalidSignature, ValueError):
        return False
