"""Encryption at rest for personally identifiable columns.

Identifying data (names, masked CNIC/phone, uploaded filenames, extracted bill
fields, free-text officer notes) is encrypted with AES-256-GCM before it reaches
SQLite, so a stolen `qistengine.db` yields ciphertext rather than a list of
applicants.

Deliberately *not* encrypted, because the queue and analytics query them in SQL:
`applicant.city`, `application.status`, `score_result.risk_band`, and every
`ScoreResult.*_json` column (pseudonymous numeric aggregates, not identifiers).
See the module docstring in `app.models` for the full split.

Storage format:  enc:v1:<urlsafe-b64( nonce[12] || AESGCM-256 ciphertext )>

A fresh nonce per write makes ciphertext non-deterministic, so encrypted columns
can never be compared with `=` in SQL. That is fine here — nothing does.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.types import Text, TypeDecorator

from app.config import get_settings

log = logging.getLogger(__name__)

PREFIX = "enc:v1:"
_NONCE_BYTES = 12
_HKDF_SALT = b"qistengine.pii.v1"
_HKDF_INFO = b"aesgcm-256"

# Development fallback. Published in source on purpose: this is a demonstration
# project on synthetic data, and a per-machine random key would mean that losing
# backend/.env silently renders the seeded demo database undecryptable. Setting
# QIST_ENV=production makes a real QIST_PII_KEY mandatory instead.
_DEV_KEY = "qistengine-development-key-not-for-real-data"

UNREADABLE = "[unreadable: encrypted with a different QIST_PII_KEY]"

_ciphers: dict[bytes, AESGCM] = {}
_warned_dev_key = False
_warned_undecryptable = False


def _derive(raw: str) -> bytes:
    """HKDF-SHA256 to 32 bytes, so any passphrase works as a key."""
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=_HKDF_SALT, info=_HKDF_INFO
    ).derive(raw.encode("utf-8"))


def _cipher() -> AESGCM:
    """Resolve the active cipher.

    `get_settings()` is called here rather than captured at import time: the API
    tests clear the settings cache and reload modules, and an import-time capture
    would go stale.
    """
    global _warned_dev_key
    settings = get_settings()
    raw = (settings.pii_key or "").strip()
    if not raw:
        if settings.env == "production":
            raise RuntimeError(
                "QIST_PII_KEY must be set when QIST_ENV=production. Generate one with:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if not _warned_dev_key:
            log.warning(
                "QIST_PII_KEY is not set — using the development key published in "
                "app/security/crypto.py. PII is encrypted at rest but NOT protected. "
                "Set QIST_PII_KEY before storing anything real."
            )
            _warned_dev_key = True
        raw = _DEV_KEY

    key = _derive(raw)
    cipher = _ciphers.get(key)
    if cipher is None:
        cipher = AESGCM(key)
        _ciphers[key] = cipher
    return cipher


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_BYTES)
    blob = nonce + _cipher().encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt(stored: str) -> str:
    """Decrypt a stored value.

    Values without the `enc:v1:` prefix are returned unchanged, so a database
    written before this feature keeps working instead of raising. Leniency
    applies on read only — writes are always encrypted.
    """
    global _warned_undecryptable
    if not stored.startswith(PREFIX):
        return stored
    blob = base64.urlsafe_b64decode(stored[len(PREFIX):].encode("ascii"))
    try:
        return _cipher().decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], None).decode("utf-8")
    except InvalidTag:
        if not _warned_undecryptable:
            log.warning(
                "A PII column could not be decrypted — the database was written with a "
                "different QIST_PII_KEY. Delete backend/data/qistengine.db and re-run "
                "`python -m app.seed` to rebuild it with the current key."
            )
            _warned_undecryptable = True
        return UNREADABLE


def reset_cache() -> None:
    """Drop memoised ciphers and one-shot warnings. For tests."""
    global _warned_dev_key, _warned_undecryptable
    _ciphers.clear()
    _warned_dev_key = False
    _warned_undecryptable = False


class EncryptedString(TypeDecorator):
    """A `str` column stored as AES-256-GCM ciphertext."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return decrypt(str(value))


class EncryptedJSON(TypeDecorator):
    """A JSON column (dict/list) stored as AES-256-GCM ciphertext."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        raw = decrypt(str(value))
        if raw == UNREADABLE:
            return {}
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
