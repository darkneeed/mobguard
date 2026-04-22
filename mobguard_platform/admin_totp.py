from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse


def generate_totp_secret(num_bytes: int = 20) -> str:
    raw = os.urandom(num_bytes)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def provisioning_uri(secret: str, account_name: str, *, issuer: str = "MobGuard") -> str:
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    params = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": 6,
            "period": 30,
        }
    )
    return f"otpauth://totp/{label}?{params}"


def current_totp_code(secret: str, *, at_time: int | None = None) -> str:
    timestamp = int(at_time or time.time())
    counter = int(timestamp // 30)
    normalized_secret = str(secret or "").strip().upper()
    padding = "=" * ((8 - len(normalized_secret) % 8) % 8)
    key = base64.b32decode(f"{normalized_secret}{padding}", casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    index = digest[-1] & 0x0F
    code_int = (
        ((digest[index] & 0x7F) << 24)
        | ((digest[index + 1] & 0xFF) << 16)
        | ((digest[index + 2] & 0xFF) << 8)
        | (digest[index + 3] & 0xFF)
    )
    return f"{code_int % 1000000:06d}"


def verify_totp_code(secret: str, code: str, *, at_time: int | None = None, window: int = 1) -> bool:
    normalized_code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(normalized_code) != 6:
        return False
    timestamp = int(at_time or time.time())
    base_counter = int(timestamp // 30)
    normalized_secret = str(secret or "").strip().upper()
    if not normalized_secret:
        return False
    padding = "=" * ((8 - len(normalized_secret) % 8) % 8)
    try:
        key = base64.b32decode(f"{normalized_secret}{padding}", casefold=True)
    except Exception:
        return False
    for offset in range(-window, window + 1):
        digest = hmac.new(key, struct.pack(">Q", base_counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 0x0F
        code_int = (
            ((digest[index] & 0x7F) << 24)
            | ((digest[index + 1] & 0xFF) << 16)
            | ((digest[index + 2] & 0xFF) << 8)
            | (digest[index + 3] & 0xFF)
        )
        if f"{code_int % 1000000:06d}" == normalized_code:
            return True
    return False
