"""WebSocket gateway client for OpenClaw."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import platform
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from uuid import uuid4

import websockets
from websockets.client import WebSocketClientProtocol

from rook.adapters.openclaw.device_auth import (
    build_device_auth_payload,
    clear_device_auth_token,
    load_device_auth_token,
    load_or_create_device_identity,
    public_key_raw_base64url_from_pem,
    sign_device_payload,
    store_device_auth_token,
)
from rook.adapters.openclaw.models import GatewayEnvelope
from rook.core.config import Config
from rook.utils.exceptions import OpenClawError, ConnectionError as RookConnectionError
from rook.utils.logging import get_logger

logger = get_logger(__name__)

OPENCLAW_OPERATOR_ROLE = "operator"
OPENCLAW_OPERATOR_SCOPES = ["operator.read", "operator.write"]


@dataclass(frozen=True)
class _OpenClawTextFragment:
    """A single assistant text fragment plus its semantic phase, when known."""

    text: str
    phase: Optional[str] = None


class OpenClawClient:
    """Client for the OpenClaw gateway websocket protocol."""

    def __init__(self, config: Config):
        self.config = config
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._incoming_queue: asyncio.Queue[GatewayEnvelope] = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None
        self._pending_replies: dict[str, asyncio.Future] = {}
        self._session_key: Optional[str] = None
        self._stream_taps: set[asyncio.Queue[GatewayEnvelope]] = set()
        self._state_dir = self.config.log_file.parent / "openclaw"
        self._device_identity_path = self._state_dir / "identity" / "device.json"
        self._device_auth_path = self._state_dir / "identity" / "device-auth.json"

    async def connect(self) -> None:
        """Open the websocket and authenticate with a `connect` message."""
        if not self.config.has_openclaw_config:
            raise RookConnectionError("OpenClaw not configured")

        if self._connected:
            return

        logger.info("Connecting to OpenClaw gateway at %s", self.config.openclaw_ws_url)
        identity = load_or_create_device_identity(self._device_identity_path)
        cached_device_token = load_device_auth_token(
            self._device_auth_path,
            device_id=identity.device_id,
            role=OPENCLAW_OPERATOR_ROLE,
        )
        attempts: list[tuple[str, str]] = []
        if cached_device_token is not None:
            attempts.append(("device token", cached_device_token.token))
        if not attempts or cached_device_token.token != self.config.openclaw_api_key:
            attempts.append(("shared token", self.config.openclaw_api_key))

        last_error: Optional[Exception] = None
        for label, auth_token in attempts:
            try:
                await self._connect_once(auth_token=auth_token, identity_path=self._device_identity_path)
                return
            except Exception as exc:
                last_error = exc
                await self.disconnect()
                if label == "device token":
                    clear_device_auth_token(
                        self._device_auth_path,
                        device_id=identity.device_id,
                        role=OPENCLAW_OPERATOR_ROLE,
                    )
                    logger.warning("Stored OpenClaw device token failed; retrying with shared token")
                    continue
                break

        assert last_error is not None
        logger.error("Failed to connect to OpenClaw: %s", last_error)
        raise RookConnectionError(f"Connection failed: {last_error}") from last_error

    async def _connect_once(self, *, auth_token: str, identity_path: Path) -> None:
        """Attempt a single websocket connect using either a device token or shared token."""
        identity = load_or_create_device_identity(identity_path)

        try:
            self._ws = await websockets.connect(self.config.openclaw_ws_url)

            raw_challenge = await asyncio.wait_for(self._ws.recv(), timeout=5)
            challenge = GatewayEnvelope.model_validate(json.loads(raw_challenge))
            nonce: Optional[str] = None
            if challenge.type == "event" and challenge.event == "connect.challenge":
                payload = challenge.payload()
                nonce_value = payload.get("nonce")
                if isinstance(nonce_value, str) and nonce_value.strip():
                    nonce = nonce_value
                logger.info("Received OpenClaw connect challenge")
            else:
                logger.warning("Unexpected first OpenClaw frame: %s", challenge.kind)

            self._reader_task = asyncio.create_task(self._reader_loop())
            signed_at_ms = int(time.time() * 1000)
            connect_payload = build_device_auth_payload(
                device_id=identity.device_id,
                client_id="cli",
                client_mode="cli",
                role=OPENCLAW_OPERATOR_ROLE,
                scopes=OPENCLAW_OPERATOR_SCOPES,
                signed_at_ms=signed_at_ms,
                token=auth_token,
                nonce=nonce,
            )

            connect_reply = await self._send_request(
                "connect",
                {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "cli",
                        "version": "0.1.0",
                        "platform": self._platform_name(),
                        "mode": "cli",
                    },
                    "role": OPENCLAW_OPERATOR_ROLE,
                    "scopes": OPENCLAW_OPERATOR_SCOPES,
                    "caps": [],
                    "auth": {"token": auth_token},
                    "device": {
                        "id": identity.device_id,
                        "publicKey": public_key_raw_base64url_from_pem(identity.public_key_pem),
                        "signature": sign_device_payload(identity.private_key_pem, connect_payload),
                        "signedAt": signed_at_ms,
                        "nonce": nonce,
                    },
                    "userAgent": "rook-agent/0.1.0",
                    "locale": "en-US",
                },
            )

            if connect_reply.error:
                raise RookConnectionError(
                    f"OpenClaw authentication failed: {connect_reply.error}"
                )

            hello = connect_reply.payload()
            self._session_key = (
                hello.get("snapshot", {})
                .get("sessionDefaults", {})
                .get("mainSessionKey")
            )
            auth_info = hello.get("auth")
            granted_scopes: list[str] = OPENCLAW_OPERATOR_SCOPES
            if isinstance(auth_info, dict):
                scopes = auth_info.get("scopes")
                if isinstance(scopes, list):
                    granted_scopes = [scope for scope in scopes if isinstance(scope, str)]
                device_token = auth_info.get("deviceToken")
                if isinstance(device_token, str) and device_token:
                    store_device_auth_token(
                        self._device_auth_path,
                        device_id=identity.device_id,
                        role=auth_info.get("role") or OPENCLAW_OPERATOR_ROLE,
                        token=device_token,
                        scopes=granted_scopes,
                    )
            self._connected = True
            logger.info(
                "Connected to OpenClaw gateway (session=%s, scopes=%s)",
                self._session_key or "unknown",
                ",".join(granted_scopes) or "none",
            )
        except Exception:
            raise

    async def disconnect(self) -> None:
        """Close the websocket and background reader."""
        self._connected = False
        self._session_key = None

        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
            self._reader_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        for future in self._pending_replies.values():
            if not future.done():
                future.cancel()
        self._pending_replies.clear()
        logger.info("Disconnected from OpenClaw")

    async def send_chat(self, content: str, session_id: Optional[str] = None) -> str:
        """Send a text chat turn through the gateway."""
        params: dict[str, Any] = {
            "message": content,
            "deliver": False,
            "idempotencyKey": str(uuid4()),
        }
        effective_session = session_id or self._session_key
        if effective_session:
            params["sessionKey"] = effective_session

        reply = await self._send_request("chat.send", params)
        if reply.error:
            raise OpenClawError(str(reply.error))
        payload = reply.payload()
        return payload.get("runId") or reply.id or ""

    async def send_task(self, description: str, session_id: Optional[str] = None) -> str:
        """Send an agent task request through the gateway."""
        params: dict[str, Any] = {"prompt": description}
        effective_session = session_id or self._session_key
        if effective_session:
            params["sessionKey"] = effective_session

        reply = await self._send_request("agent", params)
        if reply.error:
            raise OpenClawError(str(reply.error))
        return reply.id or ""

    async def receive_message(self) -> Optional[GatewayEnvelope]:
        """Receive the next streamed gateway event."""
        if not self._connected:
            return None

        try:
            return await self._incoming_queue.get()
        except asyncio.CancelledError:
            return None

    async def send_chat_and_wait_text(
        self,
        content: str,
        session_id: Optional[str] = None,
        timeout: float = 20.0,
        idle_timeout: float = 2.0,
    ) -> str:
        """Send a chat turn and wait for the streamed final assistant text."""
        run_id = await self.send_chat(content, session_id=session_id)
        if not run_id:
            raise OpenClawError("chat.send did not return a run id")

        tap: asyncio.Queue[GatewayEnvelope] = asyncio.Queue()
        self._stream_taps.add(tap)
        commentary_text = ""
        final_text = ""

        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            last_activity: Optional[float] = None

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    best_text = final_text or commentary_text
                    if best_text:
                        logger.warning(
                            "Returning OpenClaw %s reply after overall timeout (run_id=%s)",
                            "final" if final_text else "partial",
                            run_id,
                        )
                        return best_text
                    raise OpenClawError("Timed out waiting for OpenClaw streamed reply")

                waiting_for_final_inactivity = False
                if final_text and last_activity is not None:
                    inactivity_remaining = max(0.1, idle_timeout - (loop.time() - last_activity))
                    if inactivity_remaining < remaining:
                        remaining = inactivity_remaining
                        waiting_for_final_inactivity = True

                try:
                    envelope = await asyncio.wait_for(tap.get(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    if waiting_for_final_inactivity and final_text:
                        logger.info(
                            "Returning OpenClaw final reply after %.1fs of stream inactivity (run_id=%s)",
                            idle_timeout,
                            run_id,
                        )
                        return final_text
                    best_text = final_text or commentary_text
                    if best_text:
                        logger.warning(
                            "Returning OpenClaw %s reply after overall timeout (run_id=%s)",
                            "final" if final_text else "partial",
                            run_id,
                        )
                        return best_text
                    raise OpenClawError("Timed out waiting for OpenClaw streamed reply") from exc
                payload = envelope.payload()
                if payload.get("runId") != run_id:
                    continue

                logger.debug(
                    "Observed OpenClaw stream event kind=%s state=%s phase=%s run_id=%s",
                    envelope.kind,
                    payload.get("state"),
                    (payload.get("data") or {}).get("phase") if isinstance(payload.get("data"), dict) else None,
                    run_id,
                )

                for fragment in self._extract_text_fragments(payload):
                    bucket = final_text if fragment.phase == "final_answer" else commentary_text
                    merged = self._merge_text(bucket, fragment.text)
                    if fragment.phase == "final_answer":
                        final_text = merged
                    else:
                        commentary_text = merged
                    last_activity = loop.time()
                    logger.debug(
                        "OpenClaw assembled %s update (run_id=%s, chunk_chars=%s, total_chars=%s): %r",
                        fragment.phase or "unclassified",
                        run_id,
                        len(fragment.text),
                        len(merged),
                        merged[:200],
                    )

                best_text = final_text or commentary_text

                if envelope.kind.startswith("chat") and payload.get("state") == "final":
                    if not best_text:
                        logger.debug(
                            "Ignoring empty OpenClaw final chat event while waiting for assistant text (run_id=%s)",
                            run_id,
                        )
                        continue
                    logger.info(
                        "OpenClaw returning final chat reply (run_id=%s, chars=%s)",
                        run_id,
                        len(best_text),
                    )
                    return best_text

                if envelope.kind.startswith("agent"):
                    data = payload.get("data")
                    if isinstance(data, dict) and data.get("phase") == "end" and best_text:
                        logger.info(
                            "OpenClaw returning reply on agent phase=end (run_id=%s, chars=%s)",
                            run_id,
                            len(best_text),
                        )
                        return best_text
        finally:
            self._stream_taps.discard(tap)

    async def send_chat_and_stream_text(
        self,
        content: str,
        session_id: Optional[str] = None,
        timeout: float = 20.0,
        idle_timeout: float = 0.2,
    ) -> AsyncIterator[str]:
        """Send a chat turn and yield text chunks as they arrive from OpenClaw."""
        run_id = await self.send_chat(content, session_id=session_id)
        if not run_id:
            raise OpenClawError("chat.send did not return a run id")

        tap: asyncio.Queue[GatewayEnvelope] = asyncio.Queue()
        self._stream_taps.add(tap)

        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            last_activity: Optional[float] = None
            prev_assembled = ""

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return

                if prev_assembled and last_activity is not None:
                    remaining = min(remaining, max(0.1, idle_timeout - (loop.time() - last_activity)))

                try:
                    envelope = await asyncio.wait_for(tap.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    return

                payload = envelope.payload()
                if payload.get("runId") != run_id:
                    continue

                text = self._extract_text(payload)
                if text:
                    merged = self._merge_text(prev_assembled, text)
                    new_content = merged[len(prev_assembled):]
                    if new_content:
                        yield new_content
                        prev_assembled = merged
                        last_activity = loop.time()

                if envelope.kind.startswith("chat") and payload.get("state") == "final":
                    if not prev_assembled:
                        continue
                    return

                if envelope.kind.startswith("agent"):
                    data = payload.get("data")
                    if isinstance(data, dict) and data.get("phase") == "end":
                        return
        finally:
            self._stream_taps.discard(tap)

    async def _send_request(self, method: str, params: dict[str, Any]) -> GatewayEnvelope:
        """Send a request and await its direct reply envelope."""
        if not self._ws:
            raise OpenClawError("Not connected")

        message_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending_replies[message_id] = future

        await self._ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": message_id,
                    "method": method,
                    "params": params,
                }
            )
        )
        logger.info("Sent OpenClaw request %s", method)

        try:
            return await asyncio.wait_for(future, timeout=15)
        except asyncio.TimeoutError as exc:
            raise OpenClawError(f"Timeout waiting for {method} reply") from exc
        finally:
            self._pending_replies.pop(message_id, None)

    async def _reader_loop(self) -> None:
        """Read websocket traffic and fan it out to waiters or stream consumers."""
        assert self._ws is not None

        try:
            async for raw_message in self._ws:
                envelope = GatewayEnvelope.model_validate(json.loads(raw_message))
                logger.debug("Received OpenClaw message kind=%s", envelope.kind)

                if envelope.id and envelope.id in self._pending_replies:
                    future = self._pending_replies[envelope.id]
                    if not future.done():
                        future.set_result(envelope)
                    continue

                for tap in list(self._stream_taps):
                    tap.put_nowait(envelope)

                await self._incoming_queue.put(envelope)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("OpenClaw reader loop failed: %s", exc)
        finally:
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the gateway websocket is authenticated and alive."""
        return self._connected

    def _platform_name(self) -> str:
        """Normalize the local platform name for OpenClaw."""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        if system == "windows":
            return "windows"
        return system

    def _extract_text(self, payload: dict[str, Any]) -> str:
        """Flatten common streamed payloads into plain text."""
        fragments = self._extract_text_fragments(payload)
        return " ".join(fragment.text for fragment in fragments if fragment.text).strip()

    def _extract_text_fragments(self, payload: dict[str, Any]) -> list[_OpenClawTextFragment]:
        """Extract assistant text fragments and preserve their semantic phase."""
        payload_phase = self._extract_payload_text_phase(payload)
        message = payload.get("message")

        if isinstance(message, dict):
            role = message.get("role")
            if isinstance(role, str) and role and role != "assistant":
                return []

            content = message.get("content")
            if isinstance(content, list):
                fragments: list[_OpenClawTextFragment] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("type")
                    if isinstance(item_type, str) and item_type != "text":
                        continue
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        fragments.append(
                            _OpenClawTextFragment(
                                text=text.strip(),
                                phase=self._extract_item_text_phase(item) or payload_phase,
                            )
                        )
                if fragments:
                    return fragments

        if isinstance(message, str) and message.strip():
            return [_OpenClawTextFragment(text=message.strip(), phase=payload_phase)]

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("text", "delta", "message"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return [_OpenClawTextFragment(text=value.strip(), phase=payload_phase)]

        direct_text = payload.get("content") or payload.get("text") or payload.get("delta")
        if isinstance(direct_text, str) and direct_text.strip():
            return [_OpenClawTextFragment(text=direct_text.strip(), phase=payload_phase)]

        return []

    def _extract_item_text_phase(self, item: dict[str, Any]) -> Optional[str]:
        """Extract the semantic phase embedded in an OpenClaw text item."""
        phase = item.get("phase")
        if isinstance(phase, str) and phase.strip():
            return phase

        signature = item.get("textSignature")
        if not isinstance(signature, str) or not signature.strip():
            return None

        try:
            parsed = json.loads(signature)
        except json.JSONDecodeError:
            return None

        phase = parsed.get("phase")
        if isinstance(phase, str) and phase.strip():
            return phase
        return None

    def _extract_payload_text_phase(self, payload: dict[str, Any]) -> Optional[str]:
        """Infer whether a payload text belongs to commentary or the final answer."""
        data = payload.get("data")
        if isinstance(data, dict):
            phase = data.get("phase")
            if isinstance(phase, str) and phase in {"commentary", "final_answer"}:
                return phase

        state = payload.get("state")
        if state == "final":
            return "final_answer"

        message = payload.get("message")
        stop_reason: Optional[str] = None
        if isinstance(message, dict):
            raw_stop_reason = message.get("stopReason")
            if isinstance(raw_stop_reason, str) and raw_stop_reason.strip():
                stop_reason = raw_stop_reason
        if stop_reason is None:
            raw_stop_reason = payload.get("stopReason")
            if isinstance(raw_stop_reason, str) and raw_stop_reason.strip():
                stop_reason = raw_stop_reason

        if stop_reason == "toolUse":
            return "commentary"
        if stop_reason == "stop":
            return "final_answer"
        return None

    def _merge_text(self, existing: str, incoming: str) -> str:
        """Merge streamed text conservatively to avoid obvious duplication."""
        incoming = incoming.rstrip("\n")
        stripped = incoming.strip()
        if not stripped:
            return existing
        if not existing:
            return self._normalize_text(stripped)
        if stripped.startswith(existing):
            return self._normalize_text(stripped)
        if existing.startswith(stripped) or stripped in existing:
            return existing
        overlap = self._find_overlap(existing, stripped)
        if overlap:
            return self._normalize_text(f"{existing}{stripped[overlap:]}")
        if incoming[:1].isspace():
            merged = f"{existing} {stripped}"
        elif stripped.startswith(("-", "'", "’")):
            merged = f"{existing}{stripped}"
        elif stripped.startswith((".", ",", "!", "?", ";", ":", ")", "]")):
            merged = f"{existing}{stripped}"
        elif existing[-1:].isalnum() and stripped[:1].isalnum():
            merged = f"{existing}{stripped}"
        else:
            merged = f"{existing} {stripped}"
        return self._normalize_text(merged)

    def _find_overlap(self, existing: str, incoming: str) -> int:
        """Return the largest safe suffix/prefix overlap between chunks."""
        max_overlap = min(len(existing), len(incoming))
        for size in range(max_overlap, 2, -1):
            if existing.endswith(incoming[:size]):
                return size
        return 0

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace after merging streamed chunks."""
        text = " ".join(text.split())
        for punctuation in (".", ",", "!", "?", ";", ":"):
            text = text.replace(f" {punctuation}", punctuation)
        return text.strip()
