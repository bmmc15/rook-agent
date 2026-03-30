"""Pydantic models for OpenClaw API."""
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OpenClawMessage(BaseModel):
    """Base message model."""

    type: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(OpenClawMessage):
    """Chat message request."""

    type: str = "chat"
    content: str
    session_id: Optional[str] = None


class ChatResponse(OpenClawMessage):
    """Chat message response."""

    type: str = "chat_response"
    content: str
    session_id: str


class TaskRequest(OpenClawMessage):
    """Coding task request."""

    type: str = "task"
    description: str
    session_id: Optional[str] = None


class TaskResponse(OpenClawMessage):
    """Task response."""

    type: str = "task_response"
    task_id: str
    status: str
    session_id: str


class TaskProgress(OpenClawMessage):
    """Task progress update."""

    type: str = "task_progress"
    task_id: str
    progress: float
    message: str


class ErrorResponse(OpenClawMessage):
    """Error response."""

    type: str = "error"
    error: str
    code: Optional[str] = None
