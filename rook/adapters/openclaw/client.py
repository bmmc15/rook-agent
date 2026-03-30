"""WebSocket gateway client for OpenClaw."""
from __future__ import annotations

import asyncio
import json
import platform
from typing import Any, Optional
from uuid import uuid4

import websockets
from websockets.client import WebSocketClientProtocol

from rook.adapters.openclaw.models import GatewayEnvelope
from rook.core.config import Config
from rook.utils.exceptions import OpenClawError, ConnectionError as RookConnectionError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


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

    async def connect(self) -> None:
        """Open the websocket and authenticate with a `connect` message."""
        if not self.config.has_openclaw_config:
            raise RookConnectionError("OpenClaw not configured")

        if self._connected:
            return

        logger.info("Connecting to OpenClaw gateway at %s", self.config.openclaw_ws_url)
        try:
            self._ws = await websockets.connect(self.config.openclaw_ws_url)

            raw_challenge = await asyncio.wait_for(self._ws.recv(), timeout=5)
            challenge = GatewayEnvelope.model_validate(json.loads(raw_challenge))
            if challenge.type == "event" and challenge.event == "connect.challenge":
                logger.info("Received OpenClaw connect challenge")
            else:
                logger.warning("Unexpected first OpenClaw frame: %s", challenge.kind)

            self._reader_task = asyncio.create_task(self._reader_loop())

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
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write"],
                    "caps": [],
                    "auth": {"token": self.config.openclaw_api_key},
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
            self._connected = True
            logger.info(
                "Connected to OpenClaw gateway (session=%s)",
                self._session_key or "unknown",
            )
        except Exception as exc:
            await self.disconnect()
            logger.error("Failed to connect to OpenClaw: %s", exc)
            raise RookConnectionError(f"Connection failed: {exc}") from exc

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
        assembled = ""

        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            last_activity: Optional[float] = None

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    if assembled:
                        logger.warning(
                            "Returning partial OpenClaw reply after overall timeout (run_id=%s)",
                            run_id,
                        )
                        return assembled
                    raise OpenClawError("Timed out waiting for OpenClaw streamed reply")

                if assembled and last_activity is not None:
                    remaining = min(remaining, max(0.1, idle_timeout - (loop.time() - last_activity)))

                try:
                    envelope = await asyncio.wait_for(tap.get(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    if assembled:
                        logger.info(
                            "Returning OpenClaw reply after %.1fs of stream inactivity (run_id=%s)",
                            idle_timeout,
                            run_id,
                        )
                        return assembled
                    raise OpenClawError("Timed out waiting for OpenClaw streamed reply") from exc
                payload = envelope.payload()
                if payload.get("runId") != run_id:
                    continue

                logger.info(
                    "Observed OpenClaw stream event kind=%s state=%s phase=%s run_id=%s",
                    envelope.kind,
                    payload.get("state"),
                    (payload.get("data") or {}).get("phase") if isinstance(payload.get("data"), dict) else None,
                    run_id,
                )

                text = self._extract_text(payload)
                if text:
                    assembled = self._merge_text(assembled, text)
                    last_activity = loop.time()
                    logger.info(
                        "OpenClaw assembled reply update (run_id=%s, chunk_chars=%s, total_chars=%s): %r",
                        run_id,
                        len(text),
                        len(assembled),
                        assembled[:200],
                    )

                if envelope.kind.startswith("chat") and payload.get("state") == "final":
                    logger.info(
                        "OpenClaw returning final chat reply (run_id=%s, chars=%s)",
                        run_id,
                        len(assembled or text or ""),
                    )
                    return assembled or text

                if envelope.kind.startswith("agent"):
                    data = payload.get("data")
                    if isinstance(data, dict) and data.get("phase") == "end" and assembled:
                        logger.info(
                            "OpenClaw returning reply on agent phase=end (run_id=%s, chars=%s)",
                            run_id,
                            len(assembled),
                        )
                        return assembled
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
        direct_text = payload.get("content") or payload.get("text") or payload.get("delta")
        if isinstance(direct_text, str):
            return direct_text.strip()

        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("text", "delta", "message"):
                value = data.get(key)
                if isinstance(value, str):
                    return value.strip()

        message = payload.get("message")
        if isinstance(message, str):
            return message.strip()
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                chunks: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str) and text.strip():
                            chunks.append(text.strip())
                return " ".join(chunks)

        return ""

    def _merge_text(self, existing: str, incoming: str) -> str:
        """Merge streamed text conservatively to avoid obvious duplication."""
        if not incoming:
            return existing
        if not existing:
            return incoming
        if incoming.startswith(existing):
            return incoming
        if existing.startswith(incoming) or incoming in existing:
            return existing
        if not existing.endswith(" ") and not incoming.startswith((" ", ".", ",", "!", "?", ";", ":")):
            return f"{existing} {incoming}".strip()
        return f"{existing}{incoming}".strip()
