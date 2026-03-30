"""Main application orchestrator."""
import asyncio
import signal
from typing import Optional

from rich.console import Console

from rook.audio.capture import AudioCapture
from rook.audio.playback import AudioPlayback
from rook.audio.providers.base import VoiceEvent, VoiceEventType
from rook.audio.providers.gemini_live import GeminiLiveProvider
from rook.audio.waveform_processor import WaveformProcessor
from rook.cli.input_handler import InputHandler
from rook.cli.renderer import Renderer
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
        self.input_handler = InputHandler(self.state_machine, self.event_bus)
        self.voice_provider: Optional[GeminiLiveProvider] = None
        if self.config.gemini_api_key:
            self.voice_provider = GeminiLiveProvider(
                api_key=self.config.gemini_api_key,
                model=self.config.gemini_live_model,
            )

        # Task tracking
        self._tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._assistant_audio_buffer = bytearray()
        self._assistant_audio_mime_type = f"audio/pcm;rate={self.config.tts_sample_rate}"
        self._latest_user_transcript = ""
        self._latest_agent_transcript = ""
        self._turn_audio_chunks = 0
        self._turn_audio_bytes = 0
        self._response_timeout_task: Optional[asyncio.Task] = None
        self._voice_receive_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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

            if self.voice_provider:
                self.renderer.update_hint("Press Space to talk, then Space again to send")
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
            await self.audio_capture.stop()

            if self.voice_provider:
                await self.voice_provider.disconnect()

            # Stop keyboard input handling
            await self.input_handler.stop()

            # Stop renderer
            await self.renderer.stop()

            self.event_bus.unsubscribe(EventType.AUDIO_INPUT_STARTED, self._on_audio_input_started)
            self.event_bus.unsubscribe(EventType.AUDIO_INPUT_STOPPED, self._on_audio_input_stopped)

            # Stop event bus
            await self.event_bus.stop()

            self.logger.info("Shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

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

                if self.voice_provider and self.voice_provider.is_connected:
                    pcm_chunk = self._chunk_to_pcm16(audio_chunk)
                    self._turn_audio_chunks += 1
                    self._turn_audio_bytes += len(pcm_chunk)
                    await self.voice_provider.send_audio(pcm_chunk)

        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")

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
        self._turn_audio_chunks = 0
        self._turn_audio_bytes = 0
        if self._response_timeout_task and not self._response_timeout_task.done():
            self._response_timeout_task.cancel()
        self.renderer.clear_transcripts()
        self.renderer.update_hint("Listening...")
        self.logger.info("User turn started")
        if await self._ensure_voice_session():
            await self.voice_provider.begin_activity()

    async def _on_audio_input_stopped(self, event: Event) -> None:
        """Finalize the current user turn and ask Gemini to respond."""
        if not self.voice_provider or not self.voice_provider.is_connected:
            self.renderer.update_hint("Gemini voice is not connected")
            self.logger.warning("Cannot end user turn because Gemini voice is not connected")
            return

        self.logger.info(
            "User turn stopped with %s audio chunks / %s bytes",
            self._turn_audio_chunks,
            self._turn_audio_bytes,
        )

        self.state_machine.transition_to(AppState.PROCESSING)
        await self.event_bus.publish(
            Event(type=EventType.STATE_CHANGED, data={"state": AppState.PROCESSING})
        )
        self.renderer.update_hint("Thinking...")
        await self.voice_provider.end_audio()
        self._response_timeout_task = self.create_task(self._response_timeout_watchdog())

    async def _receive_voice_events(self) -> None:
        """Consume Gemini Live events and update the UI/audio output."""
        if not self.voice_provider:
            return

        async for voice_event in self.voice_provider.receive():
            try:
                await self._handle_voice_event(voice_event)
            except Exception as exc:
                self.logger.error("Error handling voice event: %s", exc)

    async def _handle_voice_event(self, voice_event: VoiceEvent) -> None:
        """Handle a translated voice provider event."""
        if voice_event.type == VoiceEventType.CONNECTED:
            self.logger.info("Voice provider connected event received")
            self.renderer.update_hint("Gemini Live connected")
            return

        if voice_event.type == VoiceEventType.DISCONNECTED:
            self.logger.info("Voice provider disconnected event received")
            if self.state_machine.current_state != AppState.IDLE:
                self.renderer.update_hint("Gemini disconnected. Press Space to retry.")
                self.state_machine.transition_to(AppState.IDLE, force=True)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
                )
            return

        if voice_event.type == VoiceEventType.ERROR:
            self.logger.error("Voice provider error event: %s", voice_event.data)
            self.renderer.update_hint(f"Voice error: {voice_event.data.get('error', 'unknown')}")
            self.state_machine.transition_to(AppState.IDLE, force=True)
            await self.event_bus.publish(
                Event(type=EventType.STATE_CHANGED, data={"state": AppState.IDLE})
            )
            return

        if voice_event.type in (VoiceEventType.TRANSCRIPT_PARTIAL, VoiceEventType.TRANSCRIPT_FINAL):
            self._cancel_response_timeout()
            source = voice_event.data.get("source")
            text = voice_event.data.get("text", "").strip()
            if not text:
                return

            if source == "input":
                self._latest_user_transcript = self._merge_transcript(
                    self._latest_user_transcript,
                    text,
                )
                self.renderer.update_user_transcript(self._latest_user_transcript)
            elif source == "output":
                self._latest_agent_transcript = self._merge_transcript(
                    self._latest_agent_transcript,
                    text,
                )
                self.renderer.update_agent_transcript(self._latest_agent_transcript)
            return

        if voice_event.type == VoiceEventType.AUDIO_DATA:
            self._cancel_response_timeout()
            if self.state_machine.current_state != AppState.SPEAKING:
                self.state_machine.transition_to(AppState.SPEAKING, force=True)
                await self.event_bus.publish(
                    Event(type=EventType.STATE_CHANGED, data={"state": AppState.SPEAKING})
                )
                self.renderer.update_hint("Speaking...")

            self._assistant_audio_buffer.extend(voice_event.data["audio"])
            self._assistant_audio_mime_type = voice_event.data.get(
                "mime_type",
                self._assistant_audio_mime_type,
            )
            return

        if voice_event.type == VoiceEventType.TURN_COMPLETE:
            self._cancel_response_timeout()
            self.logger.info(
                "Gemini turn completed with %s buffered reply bytes",
                len(self._assistant_audio_buffer),
            )
            if self._assistant_audio_buffer:
                await self.event_bus.publish(Event(type=EventType.AUDIO_OUTPUT_STARTED, data={}))
                await self.audio_playback.play(
                    bytes(self._assistant_audio_buffer),
                    mime_type=self._assistant_audio_mime_type,
                )
                await self.event_bus.publish(Event(type=EventType.AUDIO_OUTPUT_STOPPED, data={}))
                self._assistant_audio_buffer.clear()

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

    def _merge_transcript(self, existing: str, incoming: str) -> str:
        """Merge a streaming transcript delta into a stable visible sentence."""
        incoming = incoming.strip("\n")
        if not incoming:
            return existing

        if not existing:
            return incoming.strip()

        if incoming.startswith(existing):
            return incoming.strip()

        if existing.startswith(incoming):
            return existing

        if incoming in existing:
            return existing

        separator = ""
        if not existing.endswith(" ") and not incoming.startswith((" ", ".", ",", "!", "?", ";", ":")):
            separator = " "

        return f"{existing}{separator}{incoming}".strip()

    async def _ensure_voice_session(self) -> bool:
        """Ensure there is an active Gemini session and receiver task."""
        if not self.voice_provider:
            return False

        if self._voice_receive_task and self._voice_receive_task.done():
            self._voice_receive_task = None

        if self.voice_provider.is_connected and self._voice_receive_task is not None:
            return True

        try:
            await self.voice_provider.connect()
        except Exception as exc:
            self.logger.error("Failed to ensure Gemini session: %s", exc)
            self.renderer.update_hint(f"Gemini connect failed: {exc}")
            return False

        self._voice_receive_task = self.create_task(self._receive_voice_events())
        self.logger.info("Started Gemini receive loop")
        return True

    def request_shutdown(self) -> None:
        """Request app shutdown from signal handlers or key commands."""
        if self._shutdown_event.is_set():
            return

        self.logger.info("Shutdown requested")
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
