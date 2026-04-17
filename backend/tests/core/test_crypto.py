from app.core.crypto import (
    decrypt_bytes,
    decrypt_from_b64url,
    encrypt_bytes,
    encrypt_to_b64url,
)


def test_encrypt_decrypt_bytes_roundtrip() -> None:
    plaintext = b"sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx"
    blob = encrypt_bytes(plaintext)
    assert blob != plaintext
    assert len(blob) > len(plaintext) + 12
    assert decrypt_bytes(blob) == plaintext


def test_nonce_randomized() -> None:
    blob1 = encrypt_bytes(b"hello")
    blob2 = encrypt_bytes(b"hello")
    assert blob1 != blob2


def test_b64url_roundtrip_unicode() -> None:
    payload = '{"user_uid":"abc","employee_id":"員工-001"}'
    token = encrypt_to_b64url(payload)
    assert decrypt_from_b64url(token) == payload
