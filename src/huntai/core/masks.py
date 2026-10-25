"""AI 掩码原值的信封加密（BR-01/D-2：encrypted_original 仅本地、加密存储、严禁外发）。

AES-256-GCM；密钥经 HUNTAI_MASK_ENCRYPTION_KEY_REF 引用（dev 为 env:VAR，base64 的 32 字节）。
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from huntai.core.errors import ProblemError
from huntai.core.secrets import resolve_secret

_KEY_CACHE: dict[str, bytes] = {}


def _load_key(key_ref: str) -> bytes:
    if key_ref in _KEY_CACHE:
        return _KEY_CACHE[key_ref]
    try:
        raw = resolve_secret(key_ref)
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except ProblemError:
        raise
    except Exception as exc:  # noqa: BLE001 - 密钥解码失败必须 fail-fast
        raise ProblemError(status=500, detail="掩码加密密钥格式非法（需 base64 的 32 字节）") from exc
    if len(key) != 32:
        raise ProblemError(status=500, detail="掩码加密密钥长度必须为 32 字节")
    _KEY_CACHE[key_ref] = key
    return key


def mask_encrypt(original: str, *, key_ref: str) -> bytes:
    key = _load_key(key_ref)
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, original.encode(), None)


def mask_decrypt(blob: bytes, *, key_ref: str) -> str:
    key = _load_key(key_ref)
    nonce, ciphertext = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode()
