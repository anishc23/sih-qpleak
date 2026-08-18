"""Key management abstraction.

Every question and every paper gets its own AES-256 data key (a DEK). That DEK
is never stored bare: it is wrapped (encrypted) under a master key before it
touches the database.

    plaintext --AES-256-GCM(DEK)--> ciphertext        (stored in `encrypted_content`)
    DEK       --AES-256-GCM(MASTER)--> wrapped key    (stored in `wrapped_key`)

For the prototype the master key comes from the environment. The interface below
is deliberately three functions wide so it can be re-pointed at AWS KMS, Azure
Key Vault or an HSM without touching any caller -- that is the production path
described in docs/SECURITY.md.

Consequence worth stating plainly: whoever holds the master key can decrypt the
database. The prototype does not claim otherwise. What it does provide is that a
stolen database file alone is useless, and that every key retrieval is
authorised and audited.
"""

from __future__ import annotations

from app.config import settings
from app.security.crypto import decrypt, encrypt, generate_data_key

# Wrapped keys are bound to their purpose so a question key cannot be swapped in
# for a paper key by editing the database.
_AAD_QUESTION = b"securelock:question-dek:v1"
_AAD_PAPER = b"securelock:paper-dek:v1"


class KeyVaultError(Exception):
    pass


def _aad(purpose: str) -> bytes:
    if purpose == "question":
        return _AAD_QUESTION
    if purpose == "paper":
        return _AAD_PAPER
    raise KeyVaultError(f"unknown key purpose: {purpose}")


def create_wrapped_key(purpose: str = "question") -> tuple[bytes, bytes]:
    """Mint a new DEK. Returns (plaintext_dek, wrapped_dek)."""
    dek = generate_data_key()
    wrapped = encrypt_key(dek, purpose)
    return dek, wrapped


def encrypt_key(dek: bytes, purpose: str = "question") -> bytes:
    """Wrap a data key under the master key."""
    # The DEK is raw bytes; encode as latin-1 so it survives the str-based API
    # without altering any byte value.
    return encrypt(dek.decode("latin-1"), settings.master_key_bytes, _aad(purpose))


def decrypt_key(wrapped: bytes, purpose: str = "question") -> bytes:
    """Unwrap a data key. Raises if the master key is wrong or the row was edited."""
    return decrypt(wrapped, settings.master_key_bytes, _aad(purpose)).encode("latin-1")
