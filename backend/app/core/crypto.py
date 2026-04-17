import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_LEN = 12


def _get_aesgcm() -> AESGCM:
    settings = get_settings()
    raw = base64.b64decode(settings.ENCRYPTION_KEY.strip())
    if len(raw) != 32:
        raise ValueError("ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
    return AESGCM(raw)


def encrypt_bytes(plaintext: bytes, associated: bytes | None = None) -> bytes:
    """回傳 nonce||ciphertext||tag（AESGCM 已將 tag append 於 ciphertext 末端）。"""
    aes = _get_aesgcm()
    nonce = os.urandom(_NONCE_LEN)
    ct = aes.encrypt(nonce, plaintext, associated)
    return nonce + ct


def decrypt_bytes(blob: bytes, associated: bytes | None = None) -> bytes:
    if len(blob) <= _NONCE_LEN:
        raise ValueError("ciphertext too short")
    aes = _get_aesgcm()
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return aes.decrypt(nonce, ct, associated)


def encrypt_to_b64url(plaintext: str) -> str:
    blob = encrypt_bytes(plaintext.encode("utf-8"))
    return base64.urlsafe_b64encode(blob).rstrip(b"=").decode("ascii")


def decrypt_from_b64url(token: str) -> str:
    pad = "=" * (-len(token) % 4)
    blob = base64.urlsafe_b64decode(token + pad)
    return decrypt_bytes(blob).decode("utf-8")
