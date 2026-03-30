"""State machine for managing application states."""
from enum import Enum, auto
from typing import Optional, Set


class AppState(Enum):
    """Application states."""

    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    ERROR = auto()


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


class StateMachine:
    """Manages application state transitions with validation."""

    # Valid state transitions
    TRANSITIONS = {
        AppState.IDLE: {AppState.LISTENING, AppState.PROCESSING, AppState.ERROR},
        AppState.LISTENING: {AppState.IDLE, AppState.PROCESSING, AppState.ERROR},
        AppState.PROCESSING: {AppState.IDLE, AppState.SPEAKING, AppState.ERROR},
        AppState.SPEAKING: {AppState.IDLE, AppState.LISTENING, AppState.ERROR},
        AppState.ERROR: {AppState.IDLE},
    }

    def __init__(self, initial_state: AppState = AppState.IDLE):
        """Initialize state machine.

        Args:
            initial_state: Starting state (default: IDLE)
        """
        self._current_state = initial_state
        self._previous_state: Optional[AppState] = None
        self._callbacks: dict[AppState, list] = {state: [] for state in AppState}

    @property
    def current_state(self) -> AppState:
        """Get current state."""
        return self._current_state

    @property
    def previous_state(self) -> Optional[AppState]:
        """Get previous state."""
        return self._previous_state

    def can_transition_to(self, new_state: AppState) -> bool:
        """Check if transition to new state is valid.

        Args:
            new_state: Target state

        Returns:
            True if transition is valid
        """
        return new_state in self.TRANSITIONS.get(self._current_state, set())

    def transition_to(self, new_state: AppState, force: bool = False) -> None:
        """Transition to a new state.

        Args:
            new_state: Target state
            force: Skip validation if True

        Raises:
            StateTransitionError: If transition is invalid
        """
        if not force and not self.can_transition_to(new_state):
            raise StateTransitionError(
                f"Invalid transition from {self._current_state.name} to {new_state.name}"
            )

        self._previous_state = self._current_state
        self._current_state = new_state

        # Execute callbacks for new state
        for callback in self._callbacks[new_state]:
            try:
                callback(self._previous_state, new_state)
            except Exception as e:
                # Don't let callback errors break state transition
                print(f"Error in state callback: {e}")

    def reset(self) -> None:
        """Reset to IDLE state."""
        self.transition_to(AppState.IDLE, force=True)

    def on_state(self, state: AppState, callback: callable) -> None:
        """Register a callback for when entering a state.

        Args:
            state: State to watch
            callback: Function to call (receives previous_state, new_state)
        """
        self._callbacks[state].append(callback)

    def get_status_text(self) -> str:
        """Get human-readable status text for current state."""
        status_map = {
            AppState.IDLE: "Press Space to talk...",
            AppState.LISTENING: "Listening...",
            AppState.PROCESSING: "Thinking...",
            AppState.SPEAKING: "Speaking...",
            AppState.ERROR: "Error occurred. Resetting...",
        }
        return status_map[self._current_state]

    def get_orb_speed(self) -> float:
        """Get orb animation speed for current state.

        Returns:
            Delay in seconds between frames. ``0`` pauses the animation.
        """
        speed_map = {
            AppState.IDLE: 0.0,
            AppState.LISTENING: 0.0,
            AppState.PROCESSING: 0.0,
            AppState.SPEAKING: 0.15,
            AppState.ERROR: 0.0,
        }
        return speed_map[self._current_state]

    def should_show_waveform(self) -> bool:
        """Check if waveform should be visible in current state."""
        return self._current_state == AppState.LISTENING

    def __repr__(self) -> str:
        """String representation."""
        return f"<StateMachine state={self._current_state.name}>"
