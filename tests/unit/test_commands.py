"""Tests for command handlers."""
import pytest

from rook.cli.commands import CommandHandler
from rook.core.agent import Agent
from rook.core.state_machine import StateMachine
from rook.core.events import EventBus


@pytest.fixture
async def command_handler(test_config, event_bus):
    """Create command handler."""
    state_machine = StateMachine()
    agent = Agent(test_config, event_bus)
    return CommandHandler(agent, state_machine, event_bus)


@pytest.mark.asyncio
async def test_help_command(command_handler):
    """Test /help command."""
    response = await command_handler.handle_command("/help")
    assert "Available commands" in response
    assert "/quit" in response


@pytest.mark.asyncio
async def test_status_command(command_handler):
    """Test /status command."""
    response = await command_handler.handle_command("/status")
    assert "Status:" in response
    assert "State:" in response


@pytest.mark.asyncio
async def test_voice_on_command(command_handler):
    """Test /voice on command."""
    response = await command_handler.handle_command("/voice on")
    assert "enabled" in response.lower()
    assert command_handler.voice_enabled is True


@pytest.mark.asyncio
async def test_voice_off_command(command_handler):
    """Test /voice off command."""
    response = await command_handler.handle_command("/voice off")
    assert "disabled" in response.lower()
    assert command_handler.voice_enabled is False


@pytest.mark.asyncio
async def test_tasks_command(command_handler):
    """Test /tasks command."""
    response = await command_handler.handle_command("/tasks")
    assert response is not None


@pytest.mark.asyncio
async def test_unknown_command(command_handler):
    """Test unknown command."""
    response = await command_handler.handle_command("/invalid")
    assert "Unknown command" in response


@pytest.mark.asyncio
async def test_code_command_no_args(command_handler):
    """Test /code command without args."""
    response = await command_handler.handle_command("/code")
    assert "Usage" in response
