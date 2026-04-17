from uuid import uuid4

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_secret,
    hash_password,
    hash_refresh_secret,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    h = hash_password("Admin#Pass2026!")
    assert verify_password("Admin#Pass2026!", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip() -> None:
    uid = uuid4()
    token = create_access_token(uid)
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["type"] == "access"


def test_refresh_secret_hash_deterministic() -> None:
    s = generate_refresh_secret()
    assert hash_refresh_secret(s) == hash_refresh_secret(s)
    assert hash_refresh_secret(s) != hash_refresh_secret(generate_refresh_secret())
