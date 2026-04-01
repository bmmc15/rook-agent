"""Helpers for OpenClaw device identity and device-token auth."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _normalize_scopes(scopes: list[str] | None) -> list[str]:
    if not scopes:
        return []
    return sorted({scope.strip() for scope in scopes if scope and scope.strip()})


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _public_key_raw_from_pem(public_key_pem: str) -> bytes:
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _fingerprint_public_key(public_key_pem: str) -> str:
    return hashlib.sha256(_public_key_raw_from_pem(public_key_pem)).hexdigest()


@dataclass(slots=True)
class DeviceIdentity:
    """Stable Ed25519 identity used for OpenClaw device-scoped auth."""

    device_id: str
    public_key_pem: str
    private_key_pem: str


@dataclass(slots=True)
class DeviceAuthToken:
    """Cached device token issued by OpenClaw after a successful connect."""

    token: str
    role: str
    scopes: list[str]
    updated_at_ms: int


def load_or_create_device_identity(path: Path) -> DeviceIdentity:
    """Load a persisted identity or create a new one."""
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            device_id = payload.get("deviceId")
            public_key_pem = payload.get("publicKeyPem")
            private_key_pem = payload.get("privateKeyPem")
            if all(isinstance(value, str) and value for value in (device_id, public_key_pem, private_key_pem)):
                derived_id = _fingerprint_public_key(public_key_pem)
                if derived_id != device_id:
                    payload["deviceId"] = derived_id
                    _write_json(path, payload)
                    device_id = derived_id
                return DeviceIdentity(
                    device_id=device_id,
                    public_key_pem=public_key_pem,
                    private_key_pem=private_key_pem,
                )
    except Exception:
        pass

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    identity = DeviceIdentity(
        device_id=_fingerprint_public_key(public_key_pem),
        public_key_pem=public_key_pem,
        private_key_pem=private_key_pem,
    )
    _write_json(
        path,
        {
            "version": 1,
            "deviceId": identity.device_id,
            "publicKeyPem": identity.public_key_pem,
            "privateKeyPem": identity.private_key_pem,
            "createdAtMs": int(time.time() * 1000),
        },
    )
    return identity


def public_key_raw_base64url_from_pem(public_key_pem: str) -> str:
    """Return the raw 32-byte Ed25519 public key encoded as base64url."""
    return _base64url_encode(_public_key_raw_from_pem(public_key_pem))


def build_device_auth_payload(
    *,
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    signed_at_ms: int,
    token: Optional[str] = None,
    nonce: Optional[str] = None,
) -> str:
    """Build the canonical payload OpenClaw expects devices to sign."""
    version = "v2" if nonce else "v1"
    parts = [
        version,
        device_id,
        client_id,
        client_mode,
        role,
        ",".join(scopes),
        str(signed_at_ms),
        token or "",
    ]
    if version == "v2":
        parts.append(nonce or "")
    return "|".join(parts)


def sign_device_payload(private_key_pem: str, payload: str) -> str:
    """Sign a device-auth payload with the persisted Ed25519 private key."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    signature = private_key.sign(payload.encode("utf-8"))
    return _base64url_encode(signature)


def load_device_auth_token(path: Path, *, device_id: str, role: str) -> Optional[DeviceAuthToken]:
    """Load the cached device token for the given device+role."""
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or payload.get("deviceId") != device_id:
            return None
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            return None
        entry = tokens.get(role.strip())
        if not isinstance(entry, dict):
            return None
        token = entry.get("token")
        if not isinstance(token, str) or not token:
            return None
        return DeviceAuthToken(
            token=token,
            role=role.strip(),
            scopes=_normalize_scopes(entry.get("scopes")),
            updated_at_ms=int(entry.get("updatedAtMs") or 0),
        )
    except Exception:
        return None


def store_device_auth_token(
    path: Path,
    *,
    device_id: str,
    role: str,
    token: str,
    scopes: list[str] | None = None,
) -> DeviceAuthToken:
    """Persist a device token returned by the gateway hello payload."""
    normalized_role = role.strip()
    normalized_scopes = _normalize_scopes(scopes)
    payload: dict
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        payload = {}

    if payload.get("version") != 1 or payload.get("deviceId") != device_id:
        payload = {
            "version": 1,
            "deviceId": device_id,
            "tokens": {},
        }

    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        tokens = {}
        payload["tokens"] = tokens

    entry = {
        "token": token,
        "role": normalized_role,
        "scopes": normalized_scopes,
        "updatedAtMs": int(time.time() * 1000),
    }
    tokens[normalized_role] = entry
    _write_json(path, payload)
    return DeviceAuthToken(
        token=token,
        role=normalized_role,
        scopes=normalized_scopes,
        updated_at_ms=entry["updatedAtMs"],
    )


def clear_device_auth_token(path: Path, *, device_id: str, role: str) -> None:
    """Remove a cached device token when the gateway rejects it."""
    try:
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or payload.get("deviceId") != device_id:
            return
        tokens = payload.get("tokens")
        if not isinstance(tokens, dict):
            return
        normalized_role = role.strip()
        if normalized_role not in tokens:
            return
        del tokens[normalized_role]
        _write_json(path, payload)
    except Exception:
        return
