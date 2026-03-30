"""Pytest configuration and fixtures."""
import pytest
import asyncio
from pathlib import Path
import tempfile

from rook.core.config import Config
from rook.core.state_machine import StateMachine
from rook.core.events import EventBus


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration."""
    return Config(
        gemini_api_key="test_key",
        database_path=temp_dir / "test.db",
        log_file=temp_dir / "test.log",
    )


@pytest.fixture
def state_machine():
    """Create state machine."""
    return StateMachine()


@pytest.fixture
async def event_bus():
    """Create event bus."""
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()
