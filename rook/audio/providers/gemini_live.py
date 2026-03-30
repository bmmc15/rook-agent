"""Gemini Live API voice provider."""
from __future__ import annotations

from typing import AsyncIterator, Optional

from google import genai
from google.genai import types

from rook.audio.providers.base import BaseVoiceProvider, VoiceEvent, VoiceEventType
from rook.utils.exceptions import VoiceProviderError
from rook.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiLiveProvider(BaseVoiceProvider):
    """Voice provider using Google's Live API."""

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise VoiceProviderError("Gemini API key is required")

        self.api_key = api_key
        self.model_name = model
        self._client = genai.Client(api_key=api_key)
        self._live_connection = None
        self._session = None
        self._connected = False

    async def connect(self) -> None:
        """Establish a Gemini Live session."""
        if self._connected:
            return

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription={},
            output_audio_transcription={},
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                )
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                )
            ),
        )

        try:
            self._live_connection = self._client.aio.live.connect(
                model=self.model_name,
                config=config,
            )
            self._session = await self._live_connection.__aenter__()
            self._connected = True
            logger.info("Connected to Gemini Live model %s", self.model_name)
        except Exception as exc:
            logger.error("Failed to connect to Gemini Live API: %s", exc)
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
            logger.info("Disconnected from Gemini Live API")

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
            logger.debug("Sent %s bytes of audio to Gemini", len(audio_data))
        except Exception as exc:
            logger.error("Failed to send audio to Gemini: %s", exc)
            raise VoiceProviderError(f"Send failed: {exc}") from exc

    async def send_text(self, text: str) -> None:
        """Send a text turn to the live session."""
        if not self._connected or not self._session:
            raise VoiceProviderError("Not connected")

        try:
            await self._session.send_client_content(
                turns={
                    "role": "user",
                    "parts": [{"text": text}],
                },
                turn_complete=True,
            )
            logger.info("Sent text turn to Gemini: %r", text[:80])
        except Exception as exc:
            logger.error("Failed to send text to Gemini: %s", exc)
            raise VoiceProviderError(f"Send failed: {exc}") from exc

    async def begin_activity(self) -> None:
        """Mark the beginning of a push-to-talk turn."""
        if not self._connected or not self._session:
            return

        await self._session.send_realtime_input(activity_start=types.ActivityStart())
        logger.info("Sent activity_start to Gemini")

    async def end_audio(self) -> None:
        """Mark the current push-to-talk turn as finished."""
        if not self._connected or not self._session:
            return

        await self._session.send_realtime_input(activity_end=types.ActivityEnd())
        logger.info("Sent activity_end to Gemini")

    async def receive(self) -> AsyncIterator[VoiceEvent]:
        """Receive messages from Gemini Live and translate them to provider events."""
        if not self._connected or not self._session:
            raise VoiceProviderError("Not connected")

        yield VoiceEvent(type=VoiceEventType.CONNECTED, data={})

        try:
            async for message in self._session.receive():
                server_content = getattr(message, "server_content", None)
                if server_content and server_content.input_transcription:
                    logger.info(
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
                    logger.info(
                        "Gemini output transcription: %r (finished=%s)",
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

                audio_data = message.data
                if audio_data:
                    logger.info("Received %s bytes of audio from Gemini", len(audio_data))
                    mime_type = "audio/pcm"
                    if server_content and server_content.model_turn:
                        for part in server_content.model_turn.parts or []:
                            if part.inline_data and part.inline_data.mime_type:
                                mime_type = part.inline_data.mime_type
                                break

                    yield VoiceEvent(
                        type=VoiceEventType.AUDIO_DATA,
                        data={"audio": audio_data, "mime_type": mime_type},
                    )

                if server_content and server_content.turn_complete:
                    logger.info("Gemini turn complete")
                    yield VoiceEvent(type=VoiceEventType.TURN_COMPLETE, data={})

        except Exception as exc:
            logger.error("Error receiving Gemini Live response: %s", exc)
            yield VoiceEvent(type=VoiceEventType.ERROR, data={"error": str(exc)})
        finally:
            self._connected = False
            self._session = None
            self._live_connection = None
            yield VoiceEvent(type=VoiceEventType.DISCONNECTED, data={})

    @property
    def is_connected(self) -> bool:
        """Check if the provider currently has an open session."""
        return self._connected
