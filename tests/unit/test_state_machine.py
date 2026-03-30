"""Tests for state machine."""
import pytest

from rook.core.state_machine import StateMachine, AppState, StateTransitionError


def test_initial_state():
    """Test initial state is IDLE."""
    sm = StateMachine()
    assert sm.current_state == AppState.IDLE
    assert sm.previous_state is None


def test_valid_transition():
    """Test valid state transition."""
    sm = StateMachine()
    sm.transition_to(AppState.LISTENING)
    assert sm.current_state == AppState.LISTENING
    assert sm.previous_state == AppState.IDLE


def test_invalid_transition():
    """Test invalid state transition raises error."""
    sm = StateMachine()
    with pytest.raises(StateTransitionError):
        sm.transition_to(AppState.SPEAKING)  # Can't go directly from IDLE to SPEAKING


def test_force_transition():
    """Test force transition bypasses validation."""
    sm = StateMachine()
    sm.transition_to(AppState.SPEAKING, force=True)
    assert sm.current_state == AppState.SPEAKING


def test_reset():
    """Test reset returns to IDLE."""
    sm = StateMachine()
    sm.transition_to(AppState.LISTENING)
    sm.reset()
    assert sm.current_state == AppState.IDLE


def test_status_text():
    """Test status text generation."""
    sm = StateMachine()
    assert "Space" in sm.get_status_text()

    sm.transition_to(AppState.LISTENING)
    assert "Listening" in sm.get_status_text()


def test_orb_speed():
    """Test orb speed varies by state."""
    sm = StateMachine()
    idle_speed = sm.get_orb_speed()

    sm.transition_to(AppState.LISTENING)
    listening_speed = sm.get_orb_speed()

    # Listening should be faster (lower delay)
    assert listening_speed < idle_speed


def test_waveform_visibility():
    """Test waveform only visible in LISTENING state."""
    sm = StateMachine()
    assert not sm.should_show_waveform()

    sm.transition_to(AppState.LISTENING)
    assert sm.should_show_waveform()

    sm.transition_to(AppState.PROCESSING)
    assert not sm.should_show_waveform()
