"""Symmetric cryptography and canonical hashing.

We use `cryptography`'s AESGCM. Nothing here implements a primitive by hand.

Wire format for every ciphertext produced in this project:

    nonce (12 bytes) || ciphertext || GCM tag (16 bytes)

AES-GCM is authenticated encryption: a tampered ciphertext fails to decrypt
rather than silently returning garbage, which is why it is used instead of CBC.
"""

from __future__ import annotations

import hashlib
import os
import unicodedata

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_SIZE = 12
KEY_SIZE = 32  # AES-256


class DecryptionError(Exception):
    """Raised when ciphertext fails authentication (wrong key or tampering)."""


def generate_data_key() -> bytes:
    """A fresh, cryptographically secure AES-256 key. One per question/paper."""
    return AESGCM.generate_key(bit_length=256)


def encrypt(plaintext: str, key: bytes, associated_data: bytes | None = None) -> bytes:
    """AES-256-GCM encrypt, returning nonce || ciphertext || tag."""
    if len(key) != KEY_SIZE:
        raise ValueError(f"key must be {KEY_SIZE} bytes, got {len(key)}")
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), associated_data)
    return nonce + ciphertext


def decrypt(blob: bytes, key: bytes, associated_data: bytes | None = None) -> str:
    """Reverse of :func:`encrypt`. Raises DecryptionError on any tampering."""
    if len(blob) <= NONCE_SIZE:
        raise DecryptionError("ciphertext too short")
    nonce, ciphertext = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, associated_data).decode("utf-8")
    except InvalidTag as exc:
        raise DecryptionError("authentication failed: wrong key or tampered ciphertext") from exc


# ----------------------------------------------------------------------
# Hashing
# ----------------------------------------------------------------------


def canonicalize(text: str) -> str:
    """Normalise text so the same question always hashes identically.

    Unicode NFC, collapsed internal whitespace, trimmed ends. Case is preserved:
    two questions differing only in capitalisation are genuinely different
    content and should produce different hashes.
    """
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.split())


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def content_hash(text: str) -> str:
    """SHA-256 of the canonical form of a question or paper body."""
    return sha256_hex(canonicalize(text))


def keccak_id(value: str) -> bytes:
    """keccak256 of a UTF-8 string, as used for on-chain bytes32 identifiers.

    Application identifiers ("Q-000127", "USR-SETTER-04") are hashed before they
    reach the chain so no readable identifier is ever published.
    """
    from eth_utils import keccak  # provided by web3

    return keccak(text=value)
