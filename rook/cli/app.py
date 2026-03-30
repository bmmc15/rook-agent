"""Main application orchestrator."""
import asyncio
import os
import signal
import time
from typing import Optional

from rich.console import Console

from rook.audio.capture import AudioCapture
from rook.audio.playback import AudioPlayback
from rook.audio.providers.base import VoiceEvent, VoiceEventType
from rook.audio.providers.gemini_live import GeminiLiveProvider
from rook.audio.waveform_processor import WaveformProcessor
from rook.cli.commands import CommandHandler
from rook.cli.input_handler import InputHandler
from rook.cli.renderer import Renderer
from rook.core.agent import Agent
from rook.core.config import get_config
from rook.core.events import EventBus, get_event_bus, Event, EventType
from rook.core.state_machine import StateMachine, AppState
from rook.utils.logging import setup_logging, get_logger
from rook.utils.exceptions import RookError, AudioError


class RookApp:
    """Main application orchestrator."""

    def __init__(self):
        """Initialize the application."""
        # Load configuration
        self.config = get_config()

        # Setup logging
        self.logger = setup_logging(
            level=self.config.log_level,
            log_file=self.config.log_file,
            log_to_console=False,  # Use Rich UI instead
        )
        self.logger.info("Rook Agent starting...")

        # Create core components
        self.console = Console(theme=None)
        self.state_machine = StateMachine()
        self.event_bus = get_event_bus()
        self.agent = Agent(self.config, self.event_bus)
        self.command_handler = CommandHandler(self.agent, self.state_machine, self.event_bus)

        # Create renderer
        self.renderer = Renderer(
            console=self.console,
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            refresh_rate=self.config.ui_refresh_rate,
        )

        # Create audio components
        self.audio_capture = AudioCapture(self.config)
        self.audio_playback = AudioPlayback(self.config)
        self.waveform_processor = WaveformProcessor(bar_count=20)
        self.input_handler = InputHandler(
            self.state_machine,
            self.event_bus,
            on_text_submit=self._handle_text_submission,
        )
        self.stt_provider: Optional[GeminiLiveProvider] = None
        self.tts_provider: Optional[GeminiLiveProvider] = None
        if self.config.gemini_api_key:
            self.stt_provider = GeminiLiveProvider(
                api_key=self.config.gemini_api_key,
                model=self.config.gemini_live_model,
                session_label="stt",
                response_modalities=("AUDIO",),
                enable_input_transcription=True,
                system_instruction=(
                    "You are the speech-to-text front end for a real-time voice assistant. "
                    "Focus on promptly producing accurate input audio transcription. "
                    "Do not add any spoken response unless absolutely necessary."
                ),
            )
            self.tts_provider = GeminiLiveProvider(
                api_key=self.config.gemini_api_key,
                model=self.config.gemini_live_model,
                session_label="tts",
                response_modalities=("AUDIO",),
                voice_name="Kore",
            )

        # Task tracking
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._assistant_audio_buffer = bytearray()
        self._assistant_audio_mime_type = f"audio/pcm;rate={self.config.tts_sample_rate}"
        self._latest_user_transcript = ""
        self._latest_agent_transcript = ""
        self._pending_agent_transcript = ""
        self._agent_playback_started = False
        self._turn_audio_chunks = 0
        self._turn_audio_bytes = 0
        self._response_timeout_task: Optional[asyncio.Task] = None
        self._stt_turn_task: Optional[asyncio.Task] = None
        self._tts_turn_task: Optional[asyncio.Task] = None
        self._audio_send_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_requested_at: Optional[float] = None
        self._shutdown_signal_count = 0
        self._voice_turn_mode = "idle"
        self._tts_stream_active = False
        self._thinking_debug_task: Optional[asyncio.Task] = None
        self._transcript_stability_task: Optional[asyncio.Task] = None
        self._phase_timer_task: Optional[asyncio.Task] = None
        self._phase_timer_label: Optional[str] = None
        self._phase_timer_started_at: Optional[float] = None
        self._turn_started_at: Optional[float] = None
        self._turn_stopped_at: Optional[float] = None
        self._first_input_transcript_at: Optional[float] = None
        self._final_input_transcript_at: Optional[float] = None
        self._openclaw_started_at: Optional[float] = None
        self._tts_started_at: Optional[float] = None
        self._first_tts_audio_at: Optional[float] = None
        self._playback_started_at: Optional[float] = None
        self._audio_send_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=128)
        self._openclaw_request_started = False

    async def start(self) -> None:
        """Start the application."""
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_running_loop()
        self.logger.info("Starting application components...")

        try:
            # Start event bus
            await self.event_bus.start()

            # Start renderer
            await self.renderer.start()
            await self.agent.start()

            self.event_bus.subscribe(EventType.AUDIO_INPUT_STARTED, self._on_audio_input_started)
            self.event_bus.subscribe(EventType.AUDIO_INPUT_STOPPED, self._on_audio_input_stopped)

            # Start audio capture
            try:
                await self.audio_capture.start()
                # Start audio processing task
                self.create_task(self._process_audio())
            except AudioError as e:
                self.logger.warning(f"Audio not available: {e}")

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start keyboard input handling
            await self.input_handler.start()
            self.create_task(self._input_loop())

            if self.stt_provider or self.tts_provider:
                stt_ready = await self._ensure_stt_session()
                tts_ready = await self._ensure_tts_session()
                if stt_ready and self._audio_send_task is None:
                    self._audio_send_task = self.create_task(self._audio_send_loop())
                if stt_ready and tts_ready:
                    self.renderer.update_hint("Press Space to talk, then Space again to send")
                else:
                    self.renderer.update_hint("Gemini connect failed. Press Space to retry")
            else:
                self.renderer.update_hint("Set GEMINI_API_KEY in .env to enable voice replies")

            # Transition to IDLE state
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )

            self.logger.info("Application started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start application: {e}")
            await self.shutdown()
            raise

    async def run(self) -> None:
        """Run the application until shutdown."""
        await self.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        if not self._running:
            return

        self.logger.info("Shutting down...")
        self._running = False

        try:
            self._cancel_response_timeout()
            self._cancel_thinking_debug()
            self._cancel_transcript_stability()
            self._stop_phase_timer()

            # Publish shutdown event
            await self.event_bus.publish(Event(type=EventType.SYSTEM_SHUTDOWN, data={}))

            # Stop live audio output first so shutdown is never blocked behind playback
            await self.audio_playback.stop()

            # Cancel all tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)

            # Stop audio capture
            await asyncio.wait_for(self.audio_capture.stop(), timeout=2)

            if self._audio_send_task and not self._audio_send_task.done():
                self._audio_send_queue.put_nowait(None)
                await asyncio.gather(self._audio_send_task, return_exceptions=True)
                self._audio_send_task = None

            if self.stt_provider:
                await asyncio.wait_for(self.stt_provider.disconnect(), timeout=3)

            if self.tts_provider:
                await asyncio.wait_for(self.tts_provider.disconnect(), timeout=3)

            # Stop keyboard input handling
            await asyncio.wait_for(self.input_handler.stop(), timeout=1)

            # Stop renderer
            await asyncio.wait_for(self.renderer.stop(), timeout=2)

            self.event_bus.unsubscribe(EventType.AUDIO_INPUT_STARTED, self._on_audio_input_started)
            self.event_bus.unsubscribe(EventType.AUDIO_INPUT_STOPPED, self._on_audio_input_stopped)

            await self.agent.stop()

            # Stop event bus
            await asyncio.wait_for(self.event_bus.stop(), timeout=2)

            self.logger.info("Shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self._shutdown_requested_at = None
            self._shutdown_signal_count = 0

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            """Handle shutdown signals."""
            self.logger.info(f"Received signal {sig}, initiating shutdown...")
            self.request_shutdown()

        try:
            if self._loop is not None:
                self._loop.add_signal_handler(signal.SIGINT, self.request_shutdown)
                self._loop.add_signal_handler(signal.SIGTERM, self.request_shutdown)
                return
        except NotImplementedError:
            pass

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _process_audio(self) -> None:
        """Process audio stream and publish waveform events."""
        self.logger.info("Starting audio processing...")

        try:
            async for audio_chunk in self.audio_capture.stream():
                # Only process if in LISTENING state
                if self.state_machine.current_state != AppState.LISTENING:
                    continue

                # Process audio into bar heights
                bar_heights = self.waveform_processor.process(audio_chunk)

                # Publish audio level event
                await self.event_bus.publish(
                    Event(
                        type=EventType.AUDIO_LEVEL_UPDATED,
                        data={"bar_heights": bar_heights},
                    )
                )

                if self.stt_provider and self.stt_provider.is_connected:
                    pcm_chunk = self._chunk_to_pcm16(audio_chunk)
                    self._turn_audio_chunks += 1
                    self._turn_audio_bytes += len(pcm_chunk)
                    try:
                        self._audio_send_queue.put_nowait(pcm_chunk)
                    except asyncio.QueueFull:
                        self.logger.warning("Audio send queue full, dropping a microphone chunk")

        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")

    async def _audio_send_loop(self) -> None:
        """Forward captured audio to Gemini outside the microphone callback path."""
        try:
            while self._running:
                chunk = await self._audio_send_queue.get()
                if chunk is None:
                    self._audio_send_queue.task_done()
                    return

                try:
                    if self.stt_provider and self.stt_provider.is_connected:
                        await self.stt_provider.send_audio(chunk)
                except Exception as exc:
                    self.logger.error("Failed to forward microphone audio to Gemini: %s", exc)
                    self._audio_send_queue.task_done()
                    self._discard_pending_audio_chunks()
                    await self._handle_stt_transport_failure(exc)
                    return
                else:
                    self._audio_send_queue.task_done()
        except asyncio.CancelledError:
            return
        finally:
            self._audio_send_task = None

    def _discard_pending_audio_chunks(self) -> None:
        """Drop queued microphone chunks after a hard STT transport failure."""
        while True:
            try:
                chunk = self._audio_send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self._audio_send_queue.task_done()
                if chunk is None:
                    break

    async def _handle_stt_transport_failure(self, exc: Exception) -> None:
        """Reset UI and session state after a fatal microphone->Gemini failure."""
        self._cancel_response_timeout()
        self._cancel_transcript_stability()
        self._stop_phase_timer()
        self._voice_turn_mode = "idle"
        self.renderer.update_hint(f"Gemini STT unavailable: {exc}")
        self.state_machine.transition_to(AppState.IDLE, force=True)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
        )

    async def _input_loop(self) -> None:
        """Continuously poll for keyboard input."""
        self.logger.info("Starting input loop...")

        try:
            while self._running and not self._shutdown_event.is_set():
                should_continue = await self.input_handler.handle_input_loop()
                if not should_continue:
                    self._shutdown_event.set()
                    break

                await asyncio.sleep(0.05)

        except Exception as e:
            self.logger.error(f"Error in input loop: {e}")

    async def _on_audio_input_started(self, event: Event) -> None:
        """Prepare the UI for a new user turn."""
        self._assistant_audio_buffer.clear()
        self._assistant_audio_mime_type = f"audio/pcm;rate={self.config.tts_sample_rate}"
        self._latest_user_transcript = ""
        self._latest_agent_transcript = ""
        self._pending_agent_transcript = ""
        self._agent_playback_started = False
        self._turn_audio_chunks = 0
        self._turn_audio_bytes = 0
        self._voice_turn_mode = "transcribing_user"
        self._tts_stream_active = False
        self._openclaw_request_started = False
        self._turn_started_at = time.monotonic()
        self._turn_stopped_at = None
        self._first_input_transcript_at = None
        self._final_input_transcript_at = None
        self._openclaw_started_at = None
        self._tts_started_at = None
        self._first_tts_audio_at = None
        self._playback_started_at = None
        self._cancel_thinking_debug()
        self._cancel_transcript_stability()
        if self._response_timeout_task and not self._response_timeout_task.done():
            self._response_timeout_task.cancel()
        self.renderer.clear_transcripts()
        self._start_phase_timer("Listening...")
        self.logger.info("User turn started")
        if await self._prepare_stt_turn():
            await self.stt_provider.begin_activity()
            self._start_stt_turn_task()

    async def _on_audio_input_stopped(self, event: Event) -> None:
        """Finalize the current user turn and ask Gemini to respond."""
        if not self.stt_provider or not self.stt_provider.is_connected:
            self.renderer.update_hint("Gemini voice is not connected")
            self.logger.warning("Cannot end user turn because Gemini voice is not connected")
            return

        self.logger.info(
            "User turn stopped with %s audio chunks / %s bytes",
            self._turn_audio_chunks,
            self._turn_audio_bytes,
        )
        self._turn_stopped_at = time.monotonic()
        if self._turn_started_at is not None:
            self.logger.info(
                "Timing: user speech capture lasted %.2fs",
                self._turn_stopped_at - self._turn_started_at,
            )

        self.state_machine.transition_to(AppState.PROCESSING)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.PROCESSING})
        )
        self._start_phase_timer("Transcribing...")
        await self._audio_send_queue.join()
        await self.stt_provider.end_audio()
        self._response_timeout_task = self.create_task(self._response_timeout_watchdog())

    def _start_stt_turn_task(self) -> None:
        """Start consuming Gemini transcription events for the current turn."""
        if self._stt_turn_task and not self._stt_turn_task.done():
            self.logger.warning("A Gemini turn is already being consumed")
            return
        self._stt_turn_task = self.create_task(self._consume_stt_turn())

    def _start_tts_turn_task(self) -> None:
        """Start consuming Gemini audio output for the current spoken reply."""
        if self._tts_turn_task and not self._tts_turn_task.done():
            self.logger.warning("A Gemini TTS turn is already being consumed")
            return
        self._tts_turn_task = self.create_task(self._consume_tts_turn())

    async def _consume_stt_turn(self) -> None:
        """Consume Gemini transcription events for one turn while keeping the session alive."""
        if not self.stt_provider:
            return

        try:
            async for voice_event in self.stt_provider.receive_turn():
                await self._handle_stt_voice_event(voice_event)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self.logger.error("Error consuming Gemini STT turn: %s", exc)
            self.renderer.update_hint(f"Voice error: {exc}")
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
        finally:
            self._stt_turn_task = None

    async def _consume_tts_turn(self) -> None:
        """Consume Gemini TTS output events for one turn."""
        if not self.tts_provider:
            return

        try:
            async for voice_event in self.tts_provider.receive_turn():
                await self._handle_tts_voice_event(voice_event)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self.logger.error("Error consuming Gemini TTS turn: %s", exc)
            self.renderer.update_hint(f"TTS error: {exc}")
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
        finally:
            self._tts_turn_task = None

    async def _handle_stt_voice_event(self, voice_event: VoiceEvent) -> None:
        """Handle Gemini input-transcription events."""
        if voice_event.type == VoiceEventType.CONNECTED:
            self.logger.info("Gemini STT provider connected event received")
            self.renderer.update_hint("Voice connected")
            return

        if voice_event.type == VoiceEventType.DISCONNECTED:
            self.logger.info("Gemini STT provider disconnected event received")
            self._stop_phase_timer()
            self.renderer.update_hint("Gemini disconnected. Press Space to retry.")
            if self.state_machine.current_state != AppState.IDLE:
                self.state_machine.transition_to(AppState.IDLE, force=True)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
                )
            return

        if voice_event.type == VoiceEventType.ERROR:
            self.logger.error("Gemini STT provider error event: %s", voice_event.data)
            self._stop_phase_timer()
            self.renderer.update_hint(f"Voice error: {voice_event.data.get('error', 'unknown')}")
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return

        if voice_event.type in (VoiceEventType.TRANSCRIPT_PARTIAL, VoiceEventType.TRANSCRIPT_FINAL):
            self._cancel_response_timeout()
            source = voice_event.data.get("source")
            raw_text = voice_event.data.get("text", "")
            is_final = bool(voice_event.data.get("finished"))
            if not raw_text.strip():
                return

            if source == "input":
                now = time.monotonic()
                if self._first_input_transcript_at is None and self._turn_started_at is not None:
                    self._first_input_transcript_at = now
                    self.logger.info(
                        "Timing: first Gemini input transcript arrived %.2fs after user turn start",
                        self._first_input_transcript_at - self._turn_started_at,
                    )
                    if self._turn_stopped_at is not None:
                        self.logger.info(
                            "Timing: first Gemini input transcript arrived %.2fs after activity_end",
                            self._first_input_transcript_at - self._turn_stopped_at,
                        )

                self._latest_user_transcript = self._merge_input_transcript(
                    self._latest_user_transcript,
                    raw_text,
                )
                self.renderer.update_user_transcript(self._latest_user_transcript)
                if self._voice_turn_mode == "transcribing_user":
                    if self.state_machine.current_state == AppState.LISTENING:
                        self._update_phase_hint()
                    else:
                        if is_final and self._final_input_transcript_at is None:
                            self._final_input_transcript_at = now
                            if self._turn_stopped_at is not None:
                                self.logger.info(
                                    "Timing: Gemini input transcript finalized %.2fs after activity_end",
                                    self._final_input_transcript_at - self._turn_stopped_at,
                                )
                        if is_final and self._latest_user_transcript.strip():
                            self._start_openclaw_from_transcript(
                                self._latest_user_transcript.strip(),
                                reason="final transcript",
                            )
                        elif not self._openclaw_request_started:
                            self._start_phase_timer("Rook is thinking...")
                            self._schedule_transcript_stability_probe()
            return

        if voice_event.type == VoiceEventType.AUDIO_DATA:
            self.logger.debug("Ignoring unexpected audio chunk on Gemini STT session")
            return

        if voice_event.type == VoiceEventType.TURN_COMPLETE:
            self._cancel_response_timeout()
            if self._turn_stopped_at is not None:
                self.logger.info(
                    "Timing: Gemini transcription turn completed %.2fs after activity_end",
                    time.monotonic() - self._turn_stopped_at,
                )
            if self._openclaw_request_started:
                self.logger.info("Gemini transcription tail finished after OpenClaw had already started")
                return
            if self._voice_turn_mode == "transcribing_user":
                self.logger.info("Gemini transcription turn complete; routing to OpenClaw")
                self._start_openclaw_from_transcript(
                    self._latest_user_transcript.strip(),
                    reason="turn_complete",
                )

    async def _handle_tts_voice_event(self, voice_event: VoiceEvent) -> None:
        """Handle Gemini TTS output events."""
        if voice_event.type == VoiceEventType.CONNECTED:
            return

        if voice_event.type == VoiceEventType.DISCONNECTED:
            self._stop_phase_timer()
            self.renderer.update_hint("Gemini voice disconnected. Press Space to retry.")
            return

        if voice_event.type == VoiceEventType.ERROR:
            self.logger.error("Gemini TTS provider error event: %s", voice_event.data)
            self._stop_phase_timer()
            self.renderer.update_hint(f"TTS error: {voice_event.data.get('error', 'unknown')}")
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return

        if voice_event.type == VoiceEventType.TRANSCRIPT_PARTIAL:
            return

        if voice_event.type == VoiceEventType.TRANSCRIPT_FINAL:
            return

        if voice_event.type == VoiceEventType.AUDIO_DATA:
            self._cancel_response_timeout()
            if self._voice_turn_mode != "tts_speaking":
                return
            if self._first_tts_audio_at is None:
                self._first_tts_audio_at = time.monotonic()
                if self._tts_started_at is not None:
                    self.logger.info(
                        "Timing: first Gemini TTS audio chunk arrived %.2fs after TTS request",
                        self._first_tts_audio_at - self._tts_started_at,
                    )
            if not self._tts_stream_active:
                self._assistant_audio_mime_type = voice_event.data.get(
                    "mime_type",
                    self._assistant_audio_mime_type,
                )
                await self.audio_playback.start_stream(
                    mime_type=self._assistant_audio_mime_type,
                    on_start=self._on_playback_started,
                    on_chunk=self._on_playback_chunk,
                )
                self._tts_stream_active = True
            await self.audio_playback.write_chunk(voice_event.data["audio"])
            return

        if voice_event.type == VoiceEventType.TURN_COMPLETE and self._voice_turn_mode == "tts_speaking":
            self.logger.info(
                "Gemini TTS turn completed (stream_active=%s)",
                self._tts_stream_active,
            )
            if self._tts_started_at is not None:
                self.logger.info(
                    "Timing: Gemini TTS turn completed %.2fs after TTS request",
                    time.monotonic() - self._tts_started_at,
                )
            if self._tts_stream_active:
                await self.audio_playback.finish_stream()
                await self.event_bus.publish(Event(type=EventType.AUDIO_OUTPUT_STOPPED, data={}))
                self._tts_stream_active = False
                self._agent_playback_started = False
                self.renderer.update_orb_activity(0.0)

            self._stop_phase_timer()
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            self.renderer.update_hint("Press Space to talk")

    def _chunk_to_pcm16(self, audio_chunk) -> bytes:
        """Convert a float32 numpy chunk into PCM16 bytes for Gemini."""
        mono_chunk = audio_chunk
        if getattr(audio_chunk, "ndim", 1) > 1:
            mono_chunk = audio_chunk[:, 0]

        clipped = mono_chunk.clip(-1.0, 1.0)
        return (clipped * 32767).astype("int16").tobytes()

    async def _response_timeout_watchdog(self) -> None:
        """Return to idle if Gemini does not answer within a reasonable time."""
        try:
            await asyncio.sleep(12)
        except asyncio.CancelledError:
            return

        self.logger.warning(
            "Timed out waiting for Gemini response after audio turn (%s chunks, %s bytes)",
            self._turn_audio_chunks,
            self._turn_audio_bytes,
        )
        self.renderer.update_hint("Timed out waiting for Gemini. Try again.")
        self.state_machine.transition_to(AppState.IDLE, force=True)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
        )

    def _cancel_response_timeout(self) -> None:
        """Cancel the outstanding response timeout task, if any."""
        if self._response_timeout_task and not self._response_timeout_task.done():
            self._response_timeout_task.cancel()
        self._response_timeout_task = None

    def _merge_agent_transcript(self, existing: str, incoming: str, is_final: bool) -> str:
        """Merge streaming assistant text deltas into a readable sentence."""
        normalized = self._normalize_transcript_text(incoming)
        if not normalized:
            return existing

        if is_final:
            return normalized

        if not existing:
            return normalized

        if normalized.startswith(existing):
            return normalized

        if existing.startswith(normalized):
            return existing

        if normalized in existing:
            return existing

        separator = ""
        if not existing.endswith(" ") and not normalized.startswith((" ", ".", ",", "!", "?", ";", ":")):
            separator = " "

        return f"{existing}{separator}{normalized}".strip()

    def _merge_input_transcript(self, existing: str, incoming: str) -> str:
        """Merge streaming user text chunks while preserving whole words."""
        incoming = incoming.rstrip("\n")
        stripped = incoming.strip()
        if not stripped:
            return existing

        if not existing:
            return self._normalize_transcript_text(stripped)

        if stripped.startswith(existing):
            return self._normalize_transcript_text(stripped)

        if existing.startswith(stripped):
            return existing

        if incoming[:1].isspace():
            merged = f"{existing} {stripped}"
        elif stripped.startswith(("-", "'", "’")):
            merged = f"{existing}{stripped}"
        elif existing[-1:].isalnum() and stripped[:1].islower():
            merged = f"{existing}{stripped}"
        elif stripped in existing:
            merged = existing
        else:
            merged = f"{existing} {stripped}"

        return self._normalize_transcript_text(merged)

    def _normalize_transcript_text(self, text: str) -> str:
        """Clean up streaming transcript spacing for display."""
        text = " ".join(text.split())

        # Heal common ASR artifacts where letters of the same word are split apart.
        while "  " in text:
            text = text.replace("  ", " ")

        for punctuation in (".", ",", "!", "?", ";", ":"):
            text = text.replace(f" {punctuation}", punctuation)

        words = text.split(" ")
        healed_words: list[str] = []
        i = 0
        while i < len(words):
            word = words[i]
            if len(word) == 1 and word.isalpha():
                j = i
                merged = []
                while j < len(words) and len(words[j]) == 1 and words[j].isalpha():
                    merged.append(words[j])
                    j += 1
                if len(merged) >= 3:
                    healed_words.append("".join(merged))
                    i = j
                    continue

            healed_words.append(word)
            i += 1

        return " ".join(healed_words).strip()

    def _build_openclaw_voice_prompt(self, user_text: str) -> str:
        """Wrap user text with concise voice-assistant guidance for faster replies."""
        guidance = (
            "You are replying inside a real-time voice assistant. "
            "Answer in European Portuguese by default unless the user clearly uses another language. "
            "Be concise and speech-friendly. "
            "Use at most two short sentences unless the user explicitly asks for a list or detailed explanation. "
            "Do not add preambles, markdown decoration, or unnecessary formatting."
        )
        return f"{guidance}\n\nUser request: {user_text}"

    def _prepare_tts_text(self, text: str) -> str:
        """Convert markdown-heavy agent output into cleaner spoken text."""
        import re

        spoken = text
        spoken = re.sub(r"`([^`]*)`", r"\1", spoken)
        spoken = re.sub(r"\*\*([^*]+)\*\*", r"\1", spoken)
        spoken = re.sub(r"\*([^*]+)\*", r"\1", spoken)
        spoken = re.sub(r"[_#>]+", " ", spoken)
        spoken = spoken.replace("•", "-")
        spoken = spoken.replace("💪", "")
        spoken = re.sub(r"\n\s*-\s*", ". ", spoken)
        spoken = re.sub(r"\n+", ". ", spoken)
        spoken = re.sub(r"\s+", " ", spoken)
        spoken = re.sub(r"\s+([.,!?;:])", r"\1", spoken)
        return spoken.strip()

    def _on_playback_chunk(self, chunk: bytes) -> None:
        """Drive the orb from actual outgoing assistant audio."""
        if not self._loop:
            return

        audio = self._pcm16_rms(chunk)
        self._loop.call_soon_threadsafe(self.renderer.update_orb_activity, audio)

    def _on_playback_started(self) -> None:
        """Sync speaking state and transcript to the first audible playback chunk."""
        if not self._loop:
            return

        self._loop.call_soon_threadsafe(lambda: self.create_task(self._mark_playback_started()))

    async def _mark_playback_started(self) -> None:
        """Update state once playback has actually started."""
        if self._agent_playback_started:
            return

        self._agent_playback_started = True
        self._playback_started_at = time.monotonic()
        if self._tts_started_at is not None:
            self.logger.info(
                "Timing: playback started %.2fs after TTS request",
                self._playback_started_at - self._tts_started_at,
            )
        self._cancel_thinking_debug()
        self._stop_phase_timer()
        self.state_machine.transition_to(AppState.SPEAKING, force=True)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.SPEAKING})
        )
        await self.event_bus.publish(Event(type=EventType.AUDIO_OUTPUT_STARTED, data={}))
        self.renderer.update_hint("Speaking...")

        if self._pending_agent_transcript:
            self._latest_agent_transcript = self._pending_agent_transcript
            self.renderer.update_agent_transcript(self._latest_agent_transcript)

    def _pcm16_rms(self, chunk: bytes) -> float:
        """Compute a normalized RMS level from a PCM16 mono chunk."""
        if not chunk:
            return 0.0

        import numpy as np

        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0

        rms = float(np.sqrt(np.mean(samples * samples)))
        return min(1.0, rms * 6.0)

    async def _handle_text_submission(self, text: str) -> None:
        """Process a typed text turn or command."""
        self.logger.info("Received typed input: %r", text[:120])

        if text.startswith("/"):
            response = await self.command_handler.handle_command(text)
            if text.strip().lower() == "/quit":
                self.request_shutdown()
            if response:
                self._latest_user_transcript = text
                self.renderer.update_user_transcript(text)
                self._latest_agent_transcript = response
                self.renderer.update_agent_transcript(response)
            return

        self._assistant_audio_buffer.clear()
        self._pending_agent_transcript = ""
        self._latest_agent_transcript = ""
        self._latest_user_transcript = text
        self._voice_turn_mode = "awaiting_openclaw"
        self.renderer.clear_transcripts()
        self.renderer.update_user_transcript(text)

        self.state_machine.transition_to(AppState.PROCESSING, force=True)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.PROCESSING})
        )
        self.renderer.update_hint("Rook is thinking...")
        self.create_task(self._request_openclaw_reply(text))

    async def _ensure_stt_session(self) -> bool:
        """Ensure the Gemini transcription session is connected."""
        if not self.stt_provider:
            return False

        if self.stt_provider.is_connected:
            return True

        try:
            await self.stt_provider.connect()
        except Exception as exc:
            self.logger.error("Failed to ensure Gemini STT session: %s", exc)
            self.renderer.update_hint(f"Gemini STT connect failed: {exc}")
            return False

        self.logger.info("Gemini STT session ready")
        return True

    async def _ensure_tts_session(self) -> bool:
        """Ensure the Gemini speech session is connected."""
        if not self.tts_provider:
            return False

        if self.tts_provider.is_connected:
            return True

        try:
            await self.tts_provider.connect()
        except Exception as exc:
            self.logger.error("Failed to ensure Gemini TTS session: %s", exc)
            self.renderer.update_hint(f"Gemini TTS connect failed: {exc}")
            return False

        self.logger.info("Gemini TTS session ready")
        return True

    async def _prepare_stt_turn(self) -> bool:
        """Make sure the transcription session can accept a fresh turn."""
        if self._stt_turn_task and not self._stt_turn_task.done():
            self.logger.warning("Previous Gemini STT turn was still active; resetting the STT session")
            self._stt_turn_task.cancel()
            await asyncio.gather(self._stt_turn_task, return_exceptions=True)
            self._stt_turn_task = None
            if self.stt_provider:
                await self.stt_provider.disconnect()

        ready = await self._ensure_stt_session()
        if ready and self._audio_send_task is None:
            self._audio_send_task = self.create_task(self._audio_send_loop())
        return ready

    async def _prepare_tts_turn(self) -> bool:
        """Make sure the speech-output session can accept a fresh turn."""
        if self._tts_turn_task and not self._tts_turn_task.done():
            self.logger.warning("Previous Gemini TTS turn was still active; resetting the TTS session")
            self._tts_turn_task.cancel()
            await asyncio.gather(self._tts_turn_task, return_exceptions=True)
            self._tts_turn_task = None
            if self.tts_provider:
                await self.tts_provider.disconnect()

        return await self._ensure_tts_session()

    def _cancel_transcript_stability(self) -> None:
        """Cancel the speculative post-stop transcript timer."""
        if self._transcript_stability_task and not self._transcript_stability_task.done():
            self._transcript_stability_task.cancel()
        self._transcript_stability_task = None

    def _schedule_transcript_stability_probe(self) -> None:
        """Speculatively start OpenClaw when transcript text has stabilized after stop."""
        self._cancel_transcript_stability()
        if (
            self._voice_turn_mode != "transcribing_user"
            or self._turn_stopped_at is None
            or self._openclaw_request_started
            or not self._latest_user_transcript.strip()
        ):
            return
        snapshot = self._latest_user_transcript.strip()
        self._transcript_stability_task = self.create_task(
            self._transcript_stability_probe(snapshot)
        )

    async def _transcript_stability_probe(self, snapshot: str) -> None:
        """Wait briefly after the latest transcript update before routing to OpenClaw."""
        try:
            await asyncio.sleep(0.75)
        except asyncio.CancelledError:
            return

        if self._openclaw_request_started or self._voice_turn_mode != "transcribing_user":
            return

        current = self._latest_user_transcript.strip()
        if not current or current != snapshot:
            return

        self.logger.info(
            "Starting OpenClaw speculatively from stable transcript (%s chars) before Gemini final/turn_complete",
            len(current),
        )
        self._start_openclaw_from_transcript(current, reason="stable transcript")

    def _start_openclaw_from_transcript(self, text: str, *, reason: str) -> None:
        """Kick off the OpenClaw request once the transcript is good enough."""
        text = text.strip()
        if not text or self._openclaw_request_started:
            return

        self._openclaw_request_started = True
        self._cancel_transcript_stability()
        now = time.monotonic()
        if self._turn_stopped_at is not None:
            self.logger.info(
                "Timing: OpenClaw started %.2fs after activity_end based on %s",
                now - self._turn_stopped_at,
                reason,
            )
        self.logger.info(
            "Starting OpenClaw from %s (%s chars)",
            reason,
            len(text),
        )
        self._start_phase_timer("Rook is thinking... waiting for OpenClaw")
        self.create_task(self._request_openclaw_reply(text))

    async def _request_openclaw_reply(self, text: str) -> None:
        """Send the transcribed/typed text to OpenClaw and wait for the final reply."""
        text = text.strip()
        if not text:
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            self.renderer.update_hint("I didn't catch that. Press Space to try again.")
            return

        self.logger.info(
            "Starting OpenClaw reply request for %s chars of user text: %r",
            len(text),
            text[:160],
        )
        self._openclaw_started_at = time.monotonic()

        if not await self.agent.ensure_openclaw_connected():
            self.logger.warning("OpenClaw is not connected; falling back to Gemini text reply")
            self._voice_turn_mode = "tts_speaking"
            self._pending_agent_transcript = "OpenClaw is not connected."
            self._start_phase_timer("Rook is thinking... preparing voice")
            if not await self._prepare_tts_turn():
                self.renderer.update_hint("OpenClaw is not connected and Gemini is unavailable")
                self._voice_turn_mode = "idle"
                return
            self._tts_started_at = time.monotonic()
            await self.tts_provider.send_text(
                "Say exactly this text and nothing else: OpenClaw is not connected."
            )
            self._response_timeout_task = self.create_task(self._response_timeout_watchdog())
            self._start_tts_turn_task()
            return

        self._voice_turn_mode = "awaiting_openclaw"
        self._start_phase_timer("Rook is thinking... waiting for OpenClaw")
        self._start_thinking_debug(stage="openclaw")

        try:
            self.logger.info("Sending text to OpenClaw and waiting for streamed reply")
            reply_text = await self.agent.openclaw_client.send_chat_and_wait_text(
                self._build_openclaw_voice_prompt(text),
                timeout=20,
                idle_timeout=0.5,
            )
        except asyncio.TimeoutError:
            self._cancel_thinking_debug()
            self.logger.warning("Timed out waiting for OpenClaw reply")
            self.renderer.update_hint("OpenClaw timed out. Try again.")
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return
        except Exception as exc:
            self._cancel_thinking_debug()
            if "Timed out waiting for OpenClaw" in str(exc):
                self.logger.warning("Timed out waiting for OpenClaw reply")
                self.renderer.update_hint("OpenClaw timed out. Try again.")
                self._voice_turn_mode = "idle"
                self.state_machine.transition_to(AppState.IDLE, force=True)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
                )
                return

            exc_label = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self.logger.error("OpenClaw request failed: %s", exc_label)
            self.renderer.update_hint(f"OpenClaw error: {exc_label}")
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return

        self._cancel_thinking_debug()
        reply_text = reply_text.strip()
        if not reply_text:
            reply_text = "I didn't receive a reply from OpenClaw."

        self.logger.info(
            "OpenClaw reply assembled (%s chars): %r",
            len(reply_text),
            reply_text[:200],
        )
        if self._openclaw_started_at is not None:
            self.logger.info(
                "Timing: OpenClaw reply assembled %.2fs after request start",
                time.monotonic() - self._openclaw_started_at,
            )
        speech_text = self._prepare_tts_text(reply_text)
        self._pending_agent_transcript = reply_text
        self._latest_agent_transcript = ""
        self._assistant_audio_buffer.clear()
        self._assistant_audio_mime_type = f"audio/pcm;rate={self.config.tts_sample_rate}"
        self._agent_playback_started = False
        self._tts_stream_active = False
        self._voice_turn_mode = "tts_speaking"
        self._start_phase_timer("Rook is thinking... preparing voice")
        self._start_thinking_debug(stage="tts")
        if not await self._prepare_tts_turn():
            self._cancel_thinking_debug()
            self.logger.error("Failed to prepare Gemini session for TTS")
            self.renderer.update_agent_transcript(reply_text)
            self.renderer.update_hint("TTS error: could not start Gemini voice")
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return
        try:
            self.logger.info(
                "Sending %s chars to Gemini TTS: %r",
                len(speech_text),
                speech_text[:200],
            )
            self._tts_started_at = time.monotonic()
            await self.tts_provider.send_text(
                f"Say exactly this text and nothing else: {speech_text}"
            )
        except Exception as exc:
            self._cancel_thinking_debug()
            exc_label = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self.logger.error("Gemini TTS handoff failed: %s", exc_label)
            self.renderer.update_agent_transcript(reply_text)
            self.renderer.update_hint(f"TTS error: {exc_label}")
            self._voice_turn_mode = "idle"
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return
        self._response_timeout_task = self.create_task(self._response_timeout_watchdog())
        self._start_tts_turn_task()

    def _start_thinking_debug(self, stage: str) -> None:
        """Start a debug watchdog for the current waiting stage."""
        self._cancel_thinking_debug()
        self._thinking_debug_task = self.create_task(self._thinking_debug_watchdog(stage))

    def _cancel_thinking_debug(self) -> None:
        """Cancel the current thinking-stage watchdog."""
        if self._thinking_debug_task and not self._thinking_debug_task.done():
            self._thinking_debug_task.cancel()
        self._thinking_debug_task = None

    def _start_phase_timer(self, label: str) -> None:
        """Show a live elapsed timer for the current wait phase."""
        self._stop_phase_timer()
        self._phase_timer_label = label
        self._phase_timer_started_at = time.monotonic()
        self._update_phase_hint()
        self._phase_timer_task = self.create_task(self._phase_timer_loop())

    def _update_phase_hint(self) -> None:
        """Refresh the timed hint with the latest elapsed value."""
        if not self._phase_timer_label or self._phase_timer_started_at is None:
            return
        elapsed = time.monotonic() - self._phase_timer_started_at
        self.renderer.update_hint(f"{self._phase_timer_label} {elapsed:.1f}s elapsed")

    def _stop_phase_timer(self) -> None:
        """Stop the current live phase timer."""
        if self._phase_timer_task and not self._phase_timer_task.done():
            self._phase_timer_task.cancel()
        self._phase_timer_task = None
        self._phase_timer_label = None
        self._phase_timer_started_at = None

    async def _phase_timer_loop(self) -> None:
        """Update the visible phase timer while waiting."""
        try:
            while self._phase_timer_started_at is not None and self._phase_timer_label is not None:
                self._update_phase_hint()
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            return

    async def _thinking_debug_watchdog(self, stage: str) -> None:
        """Emit stage-specific debug signals while the app appears stuck."""
        checkpoints = (
            (5, "still waiting"),
            (12, "long wait"),
            (25, "very long wait"),
        )

        started = time.monotonic()
        try:
            for seconds, label in checkpoints:
                await asyncio.sleep(max(0, seconds - (time.monotonic() - started)))
                if stage == "openclaw" and self._voice_turn_mode == "awaiting_openclaw":
                    self.logger.warning(
                        "Rook thinking debug (%s): waiting on OpenClaw for %.1fs",
                        label,
                        time.monotonic() - started,
                    )
                    self.renderer.update_hint(
                        f"Rook is thinking... waiting for OpenClaw ({seconds}s)"
                    )
                elif stage == "tts" and self._voice_turn_mode == "tts_speaking":
                    self.logger.warning(
                        "Rook thinking debug (%s): waiting on Gemini TTS for %.1fs; stream_active=%s; pending_text_chars=%s",
                        label,
                        time.monotonic() - started,
                        self._tts_stream_active,
                        len(self._pending_agent_transcript),
                    )
                    self.renderer.update_hint(
                        f"Rook is thinking... waiting for voice ({seconds}s)"
                    )
                else:
                    return
        except asyncio.CancelledError:
            return

    def request_shutdown(self) -> None:
        """Request app shutdown from signal handlers or key commands."""
        self._shutdown_signal_count += 1

        if self._shutdown_event.is_set():
            self.logger.warning(
                "Shutdown requested again while already shutting down (count=%s)",
                self._shutdown_signal_count,
            )
            if self._shutdown_signal_count >= 2:
                self.logger.error("Forcing process exit after repeated shutdown request")
                os._exit(130)
            return

        self.logger.info("Shutdown requested")
        self._shutdown_requested_at = time.monotonic()
        self._shutdown_event.set()
        try:
            asyncio.create_task(self.audio_playback.stop())
        except RuntimeError:
            pass

    def create_task(self, coro) -> asyncio.Task:
        """Create and track an async task.

        Args:
            coro: Coroutine to run

        Returns:
            Created task
        """
        task = asyncio.create_task(coro)
        self._tasks.append(task)

        # Remove task when done
        def _task_done(t):
            try:
                self._tasks.remove(t)
            except ValueError:
                pass

        task.add_done_callback(_task_done)
        return task
