"""Pydantic models for the OpenClaw gateway protocol."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GatewayEnvelope(BaseModel):
    """Flexible message envelope for OpenClaw gateway traffic."""

    id: Optional[str] = None
    ok: Optional[bool] = None
    method: Optional[str] = None
    event: Optional[str] = None
    type: Optional[str] = None
    payload_data: dict[str, Any] = Field(default_factory=dict, alias="payload")
    params: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def kind(self) -> str:
        """Return the best available classifier for the message."""
        return self.event or self.method or self.type or "unknown"

    def payload(self) -> dict[str, Any]:
        """Return whichever payload object is populated."""
        if self.payload_data:
            return self.payload_data
        if self.data:
            return self.data
        if self.params:
            return self.params
        return {}
