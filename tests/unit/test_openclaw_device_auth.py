"""Tests for OpenClaw device auth helpers."""
from rook.adapters.openclaw.device_auth import (
    build_device_auth_payload,
    clear_device_auth_token,
    load_device_auth_token,
    load_or_create_device_identity,
    public_key_raw_base64url_from_pem,
    sign_device_payload,
    store_device_auth_token,
)


def test_load_or_create_device_identity_is_stable(tmp_path):
    """Persisted device identities should stay stable between loads."""
    path = tmp_path / "identity" / "device.json"

    first = load_or_create_device_identity(path)
    second = load_or_create_device_identity(path)

    assert first.device_id == second.device_id
    assert first.public_key_pem == second.public_key_pem
    assert first.private_key_pem == second.private_key_pem
    assert public_key_raw_base64url_from_pem(first.public_key_pem)


def test_device_auth_payload_uses_v2_when_nonce_present(tmp_path):
    """Nonce-bearing payloads should use the v2 format the gateway expects."""
    identity = load_or_create_device_identity(tmp_path / "identity" / "device.json")

    payload = build_device_auth_payload(
        device_id=identity.device_id,
        client_id="cli",
        client_mode="cli",
        role="operator",
        scopes=["operator.read", "operator.write"],
        signed_at_ms=1234,
        token="shared-token",
        nonce="nonce-123",
    )

    assert payload.startswith("v2|")
    assert payload.endswith("|nonce-123")
    assert sign_device_payload(identity.private_key_pem, payload)


def test_device_auth_token_store_round_trip(tmp_path):
    """Cached device tokens should round-trip by device id and role."""
    path = tmp_path / "identity" / "device-auth.json"

    entry = store_device_auth_token(
        path,
        device_id="device-1",
        role="operator",
        token="device-token",
        scopes=["operator.write", "operator.read", "operator.write"],
    )
    loaded = load_device_auth_token(path, device_id="device-1", role="operator")

    assert entry.token == "device-token"
    assert loaded is not None
    assert loaded.token == "device-token"
    assert loaded.scopes == ["operator.read", "operator.write"]

    clear_device_auth_token(path, device_id="device-1", role="operator")
    assert load_device_auth_token(path, device_id="device-1", role="operator") is None
