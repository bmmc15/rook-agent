"""Gemini Live API voice provider."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional, Sequence

from google import genai
from google.genai import types

from rook.audio.providers.base import BaseVoiceProvider, VoiceEvent, VoiceEventType
from rook.utils.exceptions import VoiceProviderError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiLiveProvider(BaseVoiceProvider):
    """Voice provider using Google's Live API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        session_label: str = "voice",
        response_modalities: Sequence[str] = ("AUDIO",),
        enable_input_transcription: bool = False,
        enable_output_transcription: bool = False,
        voice_name: Optional[str] = None,
        system_instruction: Optional[str] = None,
    ):
        if not api_key:
            raise VoiceProviderError("Gemini API key is required")

        self.api_key = api_key
        self.model_name = model
        self.session_label = session_label
        self.response_modalities = tuple(response_modalities)
        self.enable_input_transcription = enable_input_transcription
        self.enable_output_transcription = enable_output_transcription
        self.voice_name = voice_name
        self.system_instruction = system_instruction
        self._client = genai.Client(api_key=api_key)
        self._live_connection = None
        self._session = None
        self._connected = False
        self._receive_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish a Gemini Live session."""
        if self._connected:
            return

        config_kwargs = {
            "response_modalities": list(self.response_modalities),
            "realtime_input_config": types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                )
            ),
        }
        if self.enable_input_transcription:
            config_kwargs["input_audio_transcription"] = {}
        if self.enable_output_transcription:
            config_kwargs["output_audio_transcription"] = {}
        if self.voice_name:
            config_kwargs["speech_config"] = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice_name,
                    )
                )
            )
        if self.system_instruction:
            config_kwargs["system_instruction"] = self.system_instruction

        config = types.LiveConnectConfig(**config_kwargs)

        try:
            self._live_connection = self._client.aio.live.connect(
                model=self.model_name,
                config=config,
            )
            self._session = await self._live_connection.__aenter__()
            self._connected = True
            logger.info(
                "Connected to Gemini Live model %s (%s session)",
                self.model_name,
                self.session_label,
            )
        except Exception as exc:
            logger.error(
                "Failed to connect to Gemini Live API (%s session): %s",
                self.session_label,
                exc,
            )
            raise VoiceProviderError(f"Connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        """Close the Gemini Live session."""
        if not self._session:
            self._connected = False
            return

        try:
            if self._live_connection is not None:
                await self._live_connection.__aexit__(None, None, None)
            else:
                await self._session.close()
        finally:
            self._live_connection = None
            self._session = None
            self._connected = False
            logger.info("Disconnected from Gemini Live API (%s session)", self.session_label)

    async def send_audio(self, audio_data: bytes) -> None:
        """Send a PCM16 audio chunk to the live session."""
        if not self._connected or not self._session:
            raise VoiceProviderError("Not connected")

        try:
            await self._session.send_realtime_input(
                audio=types.Blob(
                    data=audio_data,
                    mime_type="audio/pcm;rate=16000",
                )
            )
            logger.debug(
                "Sent %s bytes of audio to Gemini (%s session)",
                len(audio_data),
                self.session_label,
            )
        except Exception as exc:
            try:
                await self.disconnect()
            except Exception:
                pass
            logger.error("Failed to send audio to Gemini (%s session): %s", self.session_label, exc)
            raise VoiceProviderError(f"Send failed: {exc}") from exc

    async def send_text(self, text: str) -> None:
        """Send a text turn to the live session."""
        if not self._connected or not self._session:
            raise VoiceProviderError("Not connected")

        try:
            if self.model_name.startswith("gemini-3.1-"):
                await self._session.send_realtime_input(text=text)
            else:
                await self._session.send_client_content(
                    turns={
                        "role": "user",
                        "parts": [{"text": text}],
                    },
                    turn_complete=True,
                )
            logger.info(
                "Sent text turn to Gemini (%s session): %r",
                self.session_label,
                text[:80],
            )
        except Exception as exc:
            logger.error("Failed to send text to Gemini (%s session): %s", self.session_label, exc)
            raise VoiceProviderError(f"Send failed: {exc}") from exc

    async def begin_activity(self) -> None:
        """Mark the beginning of a push-to-talk turn."""
        if not self._connected or not self._session:
            return

        await self._session.send_realtime_input(activity_start=types.ActivityStart())
        logger.info("Sent activity_start to Gemini (%s session)", self.session_label)

    async def end_audio(self) -> None:
        """Mark the current push-to-talk turn as finished."""
        if not self._connected or not self._session:
            return

        await self._session.send_realtime_input(activity_end=types.ActivityEnd())
        logger.info("Sent activity_end to Gemini (%s session)", self.session_label)

    async def receive_turn(self) -> AsyncIterator[VoiceEvent]:
        """Receive messages for a single Gemini turn while keeping the session open."""
        if not self._connected or not self._session:
            raise VoiceProviderError("Not connected")

        async with self._receive_lock:
            try:
                async for message in self._session.receive():
                    server_content = getattr(message, "server_content", None)
                    if server_content and server_content.input_transcription:
                        logger.debug(
                            "Gemini input transcription: %r (finished=%s)",
                            server_content.input_transcription.text,
                            server_content.input_transcription.finished,
                        )

                    if server_content and server_content.input_transcription:
                        transcription = server_content.input_transcription
                        yield VoiceEvent(
                            type=(
                                VoiceEventType.TRANSCRIPT_FINAL
                                if transcription.finished
                                else VoiceEventType.TRANSCRIPT_PARTIAL
                            ),
                            data={
                                "source": "input",
                                "text": transcription.text or "",
                                "finished": bool(transcription.finished),
                            },
                        )

                    if server_content and server_content.output_transcription:
                        logger.debug(
                            "Gemini output transcription (%s session): %r (finished=%s)",
                            self.session_label,
                            server_content.output_transcription.text,
                            server_content.output_transcription.finished,
                        )
                        transcription = server_content.output_transcription
                        yield VoiceEvent(
                            type=(
                                VoiceEventType.TRANSCRIPT_FINAL
                                if transcription.finished
                                else VoiceEventType.TRANSCRIPT_PARTIAL
                            ),
                            data={
                                "source": "output",
                                "text": transcription.text or "",
                                "finished": bool(transcription.finished),
                            },
                        )

                    if server_content and server_content.model_turn:
                        for part in server_content.model_turn.parts or []:
                            inline_data = getattr(part, "inline_data", None)
                            if inline_data and inline_data.data:
                                logger.debug(
                                    "Received %s bytes of audio from Gemini (%s session)",
                                    len(inline_data.data),
                                    self.session_label,
                                )
                                yield VoiceEvent(
                                    type=VoiceEventType.AUDIO_DATA,
                                    data={
                                        "audio": inline_data.data,
                                        "mime_type": inline_data.mime_type or "audio/pcm",
                                    },
                                )
                            elif getattr(part, "text", None):
                                yield VoiceEvent(
                                    type=VoiceEventType.TRANSCRIPT_PARTIAL,
                                    data={
                                        "source": "output",
                                        "text": part.text,
                                        "finished": False,
                                    },
                                )

                    if server_content and server_content.turn_complete:
                        logger.info("Gemini turn complete (%s session)", self.session_label)
                        yield VoiceEvent(type=VoiceEventType.TURN_COMPLETE, data={})
                        return

            except Exception as exc:
                logger.error(
                    "Error receiving Gemini Live response (%s session): %s",
                    self.session_label,
                    exc,
                )
                self._connected = False
                self._session = None
                self._live_connection = None
                yield VoiceEvent(type=VoiceEventType.ERROR, data={"error": str(exc)})

    async def reconnect(self, max_retries: int = 3) -> bool:
        """Attempt to reconnect with exponential backoff."""
        for attempt in range(max_retries):
            try:
                await self.disconnect()
                delay = min(2 ** attempt, 8)
                logger.info(
                    "Reconnecting Gemini Live (%s session), attempt %d/%d after %.1fs",
                    self.session_label, attempt + 1, max_retries, delay,
                )
                await asyncio.sleep(delay)
                await self.connect()
                return True
            except Exception as exc:
                logger.warning(
                    "Reconnect attempt %d/%d failed (%s session): %s",
                    attempt + 1, max_retries, self.session_label, exc,
                )
        return False

    @property
    def is_connected(self) -> bool:
        """Check if the provider currently has an open session."""
        return self._connected
