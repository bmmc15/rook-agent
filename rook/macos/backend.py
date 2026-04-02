"""JSON-line bridge between the Python runtime and the macOS menu bar app."""
import asyncio
import json
import sys
from typing import Any

from rook.cli.app import RookApp
from rook.macos.bridge_renderer import BridgeRenderer


class MenuBarBackend:
    """Host the Rook runtime for the native macOS shell."""

    def __init__(self) -> None:
        self._write_lock = asyncio.Lock()
        self._renderer = None
        self._app = None

    async def run(self) -> int:
        """Run the backend command loop until shutdown."""
        self._renderer = BridgeRenderer(
            state_machine=None,  # populated after app init
            event_bus=None,  # populated after app init
            emit_event=self.emit,
        )

        self._app = RookApp(renderer=self._renderer, enable_input_handler=False)
        self._renderer.configure_runtime(
            state_machine=self._app.state_machine,
            event_bus=self._app.event_bus,
        )

        try:
            await self._app.start()
            await self.emit(
                {
                    "type": "ready",
                    "state": self._app.state_machine.current_state.name.lower(),
                    "mode": self._app.conversation_mode,
                    "voice_configured": bool(
                        self._app.stt_provider or self._app.tts_provider or self._app.audio_mode_provider
                    ),
                    "openclaw_configured": self._app.config.has_openclaw_config,
                }
            )
            await self.command_loop()
            return 0
        finally:
            if self._app is not None:
                await self._app.shutdown()

    async def command_loop(self) -> None:
        """Consume commands from stdin until the bridge closes."""
        while True:
            raw_line = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not raw_line:
                return

            line = raw_line.decode("utf-8").strip()
            if not line:
                continue

            try:
                command = json.loads(line)
            except json.JSONDecodeError as exc:
                await self.emit({"type": "error", "message": f"Invalid JSON command: {exc}"})
                continue

            if await self.handle_command(command):
                return

    async def handle_command(self, command: dict[str, Any]) -> bool:
        """Dispatch one native-shell command. Return True when shutdown is requested."""
        if self._app is None:
            await self.emit({"type": "error", "message": "Backend is not ready"})
            return False

        command_type = command.get("type", "")

        try:
            if command_type == "ping":
                await self.emit({"type": "pong"})
                return False

            if command_type == "send_text":
                text = str(command.get("text", "")).strip()
                if not text:
                    await self.emit({"type": "command_result", "command": command_type, "ok": False})
                    return False
                await self._app.submit_text(text)
                await self.emit({"type": "command_result", "command": command_type, "ok": True})
                return False

            if command_type == "start_listening":
                started = await self._app.start_listening()
                await self.emit({"type": "command_result", "command": command_type, "ok": started})
                return False

            if command_type == "stop_listening":
                stopped = await self._app.stop_listening()
                await self.emit({"type": "command_result", "command": command_type, "ok": stopped})
                return False

            if command_type == "hard_stop_voice":
                stopped = await self._app.hard_stop_voice()
                await self.emit({"type": "command_result", "command": command_type, "ok": stopped})
                return False

            if command_type == "set_mode":
                mode = str(command.get("mode", "")).strip().lower()
                if mode not in {self._app.MODE_AGENT, self._app.MODE_AUDIO}:
                    await self.emit({"type": "command_result", "command": command_type, "ok": False})
                    return False
                message = self._app.set_conversation_mode(mode)
                await self.emit(
                    {
                        "type": "mode",
                        "mode": self._app.conversation_mode,
                        "message": message,
                    }
                )
                await self.emit({"type": "command_result", "command": command_type, "ok": True})
                return False

            if command_type == "snapshot":
                await self.emit(
                    {
                        "type": "snapshot",
                        "state": self._app.state_machine.current_state.name.lower(),
                        "mode": self._app.conversation_mode,
                    }
                )
                return False

            if command_type == "shutdown":
                await self.emit({"type": "command_result", "command": command_type, "ok": True})
                self._app.request_shutdown()
                return True

            await self.emit(
                {
                    "type": "error",
                    "message": f"Unknown command: {command_type}",
                }
            )
            return False
        except Exception as exc:
            await self.emit(
                {
                    "type": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "command": command_type,
                }
            )
            return False

    async def emit(self, payload: dict[str, Any]) -> None:
        """Write one JSON event to stdout."""
        serialized = json.dumps(payload, ensure_ascii=False)
        async with self._write_lock:
            sys.stdout.write(serialized + "\n")
            sys.stdout.flush()


async def main() -> int:
    """Entry point used by `python -m rook.macos.backend`."""
    backend = MenuBarBackend()
    return await backend.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
