# Rook Agent

A production-ready terminal voice assistant with HALIST-style UI. Combines text chat and voice interaction, connects to OpenClaw agents, and supports autonomous coding task delegation.

## Features

- **Rich Terminal UI**: Bordered panel with animated pulsating orb and green audio waveform bars
- **Voice Interaction**: Push-to-talk with Google Gemini Live API for STT+TTS
- **Text REPL**: Full command system for control and task management
- **OpenClaw Integration**: WebSocket connection to remote AI coding agents
- **Task Management**: Delegate and track autonomous coding tasks
- **Persistent Storage**: SQLite database for sessions, messages, and task history

## Requirements

- Python 3.9+ (3.11+ recommended)
- pip (uv recommended but not required)
- Microphone and speakers (for voice features)
- Gemini API key (get from https://makersuite.google.com/app/apikey)
- OpenClaw VPS endpoint (optional for coding tasks)

## Installation

```bash
# Clone the repository
cd rook-agent

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# At minimum, you need GEMINI_API_KEY (leave it blank for UI-only demo)
# Optional: OPENCLAW_WS_URL, OPENCLAW_API_KEY for coding tasks

# Install dependencies with pip
python3 -m pip install rich sounddevice numpy websockets httpx aiosqlite \
  python-dotenv "pydantic>=2.5.0" "pydantic-settings>=2.1.0" "google-generativeai>=0.3.0"

# Or install with uv (if available)
uv sync
```

## Quick Start

```bash
# Start the assistant
python3 main.py

# You should see the animated orb in a bordered panel
# Press Ctrl+C to exit
```

## Usage

### UI Demo Mode

The application starts with an animated orb visualization. This works without any API keys and demonstrates the core UI.

### Voice Interaction (Requires Gemini API Key)

1. Configure `GEMINI_API_KEY` in `.env`
2. Run `python3 main.py`
3. Press **Space** to start recording
4. Speak your message
5. Release **Space** to send
6. Rook will respond with voice and text

**Note**: Full voice integration is a work in progress. The mock provider can be used for testing.

### Text Commands

- `/help` - Show all available commands
- `/status` - Show current session status and connection info
- `/tasks` - List all coding tasks
- `/voice on|off` - Toggle voice mode
- `/code <description>` - Create a coding task (requires OpenClaw)
- `/quit` - Exit the application gracefully
- `/panic` - Emergency stop all tasks

### OpenClaw Integration (Optional)

For autonomous coding task delegation:

1. Set up an OpenClaw agent on your VPS
2. Configure in `.env`:
   ```
   OPENCLAW_WS_URL=wss://your-vps.com/ws
   OPENCLAW_API_KEY=your_bearer_token
   GEMINI_VOICE_NAME=Kore
   ```
3. Use `/code "your task description"` to delegate tasks

## Architecture

```
┌──────────────── ROOK ─────────────────┐
│                                        │
│          ░▒▓████▓▒░                    │  ← Animated orb
│        ▒▓████████████▓▒                │
│        ░▒▓████████▓▒░                  │
│                                        │
│  You ▂▄▆█▇▅▃▂▁▂▃▅▆▄▂                  │  ← Audio waveform
│                                        │
│  Listening...  Ctrl+C to quit          │  ← Status
└────────────────────────────────────────┘
```

### State Machine

- **IDLE**: Waiting for input
- **LISTENING**: Recording audio (waveform visible)
- **PROCESSING**: Analyzing request
- **SPEAKING**: Playing TTS response

### Tech Stack

- **Terminal UI**: Rich (Live display)
- **Audio**: sounddevice + numpy
- **Voice**: Google Gemini Live API
- **WebSocket**: websockets
- **Database**: aiosqlite
- **Config**: pydantic-settings

## Project Structure

```
rook-agent/
├── main.py                 # Entry point
├── rook/
│   ├── cli/               # Terminal UI components
│   │   ├── app.py        # Main application orchestrator
│   │   ├── renderer.py   # Rich Live display loop
│   │   ├── repl.py       # Command-line interface
│   │   ├── commands.py   # Command handlers
│   │   └── widgets/      # UI components (orb, waveform, status)
│   ├── audio/            # Audio processing
│   │   ├── capture.py    # Microphone input
│   │   ├── playback.py   # Audio output
│   │   ├── waveform_processor.py  # FFT visualization
│   │   └── providers/    # Voice service integrations
│   ├── core/             # Core system
│   │   ├── config.py     # Configuration management
│   │   ├── state_machine.py  # Application states
│   │   ├── events.py     # Event bus
│   │   ├── agent.py      # Central coordinator
│   │   └── message_router.py  # Message routing logic
│   ├── adapters/         # External service adapters
│   │   └── openclaw/     # OpenClaw WebSocket client
│   ├── tasks/            # Task management
│   │   ├── manager.py    # Task lifecycle
│   │   ├── executor.py   # Task execution
│   │   └── states.py     # Task state definitions
│   ├── storage/          # Data persistence
│   │   ├── database.py   # SQLite connection
│   │   ├── schema.sql    # Database schema
│   │   └── repositories/ # Data access layer
│   └── utils/            # Utilities
│       ├── logging.py    # Logging setup
│       └── exceptions.py # Custom exceptions
└── tests/                # Test suite
    ├── unit/             # Unit tests
    └── integration/      # Integration tests (stubs)
```

## Configuration

All configuration is done via `.env` file:

### Audio Settings
```bash
AUDIO_SAMPLE_RATE=16000      # Audio sample rate in Hz
AUDIO_CHANNELS=1             # 1=mono, 2=stereo
AUDIO_CHUNK_SIZE=1024        # Buffer size
# AUDIO_DEVICE_INDEX=        # Leave commented for default device
```

### UI Settings
```bash
UI_REFRESH_RATE=30           # FPS for UI updates
UI_BORDER_COLOR=magenta      # Border color
UI_WAVEFORM_COLOR=green      # Waveform bar color
UI_ORB_COLOR=red             # Orb color
```

### Voice Settings
```bash
VOICE_ACTIVATION_KEY=space   # Key to trigger voice input
BARGE_IN_THRESHOLD=0.3       # Interrupt sensitivity (0-1)
VOICE_TIMEOUT_SECONDS=5      # Max recording duration
GEMINI_VOICE_NAME=Kore       # Keep the same Gemini voice for all replies
```

### Logging
```bash
LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR
LOG_FILE=./data/rook.log     # Log file path
```

## Development

### Running Tests

```bash
# Install test dependencies
python3 -m pip install pytest pytest-asyncio

# Run all tests
python3 -m pytest tests/ -v

# Run only unit tests
python3 -m pytest tests/unit -v

# Run with coverage (if pytest-cov installed)
python3 -m pytest tests/ --cov=rook --cov-report=html
```

**Test Results**: ✅ 34 tests passing

### Code Quality

```bash
# Install dev tools (optional)
python3 -m pip install black ruff

# Format code
black rook/ tests/

# Lint
ruff check rook/ tests/
```

## Troubleshooting

### Audio Device Issues

If you get audio device errors:

1. Check available devices:
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   ```

2. Set specific device in `.env`:
   ```bash
   AUDIO_DEVICE_INDEX=0  # Use device ID from above
   ```

### Gemini API Issues

- Verify API key is valid
- Check quota at https://makersuite.google.com/
- Ensure API key has Gemini access enabled

### WebSocket Connection Issues

- Verify OpenClaw URL is accessible
- Check bearer token is correct
- Ensure firewall allows WebSocket connections

### Database Issues

- Check `./data/` directory permissions
- Delete `./data/rook.db` to reset database

## Implementation Status

### ✅ Completed
- Core foundation (config, state machine, events)
- Rich terminal UI with animated orb
- Audio capture and waveform visualization
- Voice provider abstraction
- OpenClaw adapter (WebSocket client)
- Agent and message routing
- REPL command system
- Task management system
- SQLite storage layer
- Comprehensive unit tests (34 passing)

### 🚧 In Progress
- Full voice pipeline (STT→Agent→TTS)
- Keyboard input handling for voice activation
- Gemini Live API integration

### 📋 Planned
- Session management UI
- Task progress visualization
- Voice response streaming
- Barge-in implementation
- Integration tests

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT

## Acknowledgments

- Inspired by HALIST terminal aesthetic
- Built with Rich terminal framework
- Powered by Google Gemini for voice services
