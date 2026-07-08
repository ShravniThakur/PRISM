from app.crypto import keys, signing


def test_sign_verify_roundtrip():
    private_pem, public_pem = keys.generate_keypair()
    message = b"prism payload"
    signature = signing.sign(private_pem, message)
    assert signing.verify(public_pem, message, signature)


def test_tampered_message_fails():
    private_pem, public_pem = keys.generate_keypair()
    signature = signing.sign(private_pem, b"original")
    assert not signing.verify(public_pem, b"tampered", signature)


def test_wrong_key_fails():
    private_pem, _ = keys.generate_keypair()
    _, other_public = keys.generate_keypair()
    signature = signing.sign(private_pem, b"message")
    assert not signing.verify(other_public, b"message", signature)


def test_garbage_signature_fails():
    _, public_pem = keys.generate_keypair()
    assert not signing.verify(public_pem, b"message", "not-base64!!!")
