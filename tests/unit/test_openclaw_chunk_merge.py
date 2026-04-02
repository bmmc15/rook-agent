"""Tests for OpenClaw streamed text merging."""

import asyncio
import json
from pathlib import Path

import pytest

from rook.adapters.openclaw.client import OpenClawClient
from rook.adapters.openclaw.models import GatewayEnvelope
from rook.core.config import Config


def _build_client(tmp_path) -> OpenClawClient:
    config = Config(
        log_file=Path(tmp_path) / "rook.log",
        database_path=Path(tmp_path) / "rook.db",
    )
    return OpenClawClient(config)


def test_merge_text_keeps_word_continuations_together(tmp_path):
    """Streaming continuations should not add spaces inside words."""
    client = _build_client(tmp_path)

    merged = client._merge_text("A casa que mais gostaste foi Avenidas Nov", "as.")

    assert merged == "A casa que mais gostaste foi Avenidas Novas."


def test_merge_text_uses_overlap_without_duplication(tmp_path):
    """Overlapping chunks should collapse into a single readable sentence."""
    client = _build_client(tmp_path)

    merged = client._merge_text("A casa de Avenidas Nov", "Novas está em primeiro lugar.")

    assert merged == "A casa de Avenidas Novas está em primeiro lugar."


def _gateway_event(kind: str, payload: dict) -> GatewayEnvelope:
    return GatewayEnvelope.model_validate(
        {
            "type": "event",
            "event": kind,
            "payload": payload,
        }
    )


async def _wait_for_tap(client: OpenClawClient) -> asyncio.Queue[GatewayEnvelope]:
    for _ in range(50):
        if client._stream_taps:
            return next(iter(client._stream_taps))
        await asyncio.sleep(0)
    raise AssertionError("OpenClaw stream tap was never registered")


@pytest.mark.asyncio
async def test_wait_text_prefers_final_answer_over_commentary(tmp_path, monkeypatch):
    """Commentary should not end the wait if a later final answer arrives."""
    client = _build_client(tmp_path)
    run_id = "run-slides"

    async def fake_send_chat(content: str, session_id=None) -> str:
        return run_id

    monkeypatch.setattr(client, "send_chat", fake_send_chat)

    async def emit_events() -> None:
        tap = await _wait_for_tap(client)
        tap.put_nowait(
            _gateway_event(
                "agent.message",
                {
                    "runId": run_id,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Vou avancar os slides automaticamente.",
                                "textSignature": json.dumps({"phase": "commentary"}),
                            }
                        ],
                        "stopReason": "toolUse",
                    },
                },
            )
        )
        await asyncio.sleep(0.08)
        tap.put_nowait(
            _gateway_event(
                "agent.message",
                {
                    "runId": run_id,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Carrega Comando Enter para eu continuar ate ao fim.",
                                "textSignature": json.dumps({"phase": "final_answer"}),
                            }
                        ],
                        "stopReason": "stop",
                    },
                },
            )
        )
        tap.put_nowait(
            _gateway_event(
                "agent.status",
                {
                    "runId": run_id,
                    "data": {"phase": "end"},
                },
            )
        )

    result_task = asyncio.create_task(
        client.send_chat_and_wait_text("prompt", timeout=0.5, idle_timeout=0.05)
    )
    producer_task = asyncio.create_task(emit_events())

    result = await result_task
    await producer_task

    assert result == "Carrega Comando Enter para eu continuar ate ao fim."


@pytest.mark.asyncio
async def test_wait_text_returns_commentary_when_run_ends_without_final_answer(tmp_path, monkeypatch):
    """Runs without a final_answer should still return the last useful commentary."""
    client = _build_client(tmp_path)
    run_id = "run-simple"

    async def fake_send_chat(content: str, session_id=None) -> str:
        return run_id

    monkeypatch.setattr(client, "send_chat", fake_send_chat)

    async def emit_events() -> None:
        tap = await _wait_for_tap(client)
        tap.put_nowait(
            _gateway_event(
                "agent.message",
                {
                    "runId": run_id,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Done. Mudei para o proximo slide.",
                                "textSignature": json.dumps({"phase": "commentary"}),
                            }
                        ],
                        "stopReason": "toolUse",
                    },
                },
            )
        )
        tap.put_nowait(
            _gateway_event(
                "agent.status",
                {
                    "runId": run_id,
                    "data": {"phase": "end"},
                },
            )
        )

    result_task = asyncio.create_task(
        client.send_chat_and_wait_text("prompt", timeout=0.5, idle_timeout=0.05)
    )
    producer_task = asyncio.create_task(emit_events())

    result = await result_task
    await producer_task

    assert result == "Done. Mudei para o proximo slide."


@pytest.mark.asyncio
async def test_wait_text_ignores_empty_chat_final_until_agent_text_arrives(tmp_path, monkeypatch):
    """An empty chat.final event must not mask the later agent reply."""
    client = _build_client(tmp_path)
    run_id = "run-empty-final"

    async def fake_send_chat(content: str, session_id=None) -> str:
        return run_id

    monkeypatch.setattr(client, "send_chat", fake_send_chat)

    async def emit_events() -> None:
        tap = await _wait_for_tap(client)
        tap.put_nowait(
            _gateway_event(
                "chat.message",
                {
                    "runId": run_id,
                    "state": "final",
                },
            )
        )
        await asyncio.sleep(0.02)
        tap.put_nowait(
            _gateway_event(
                "agent.message",
                {
                    "runId": run_id,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "Vou continuar a apresentacao automaticamente ate ao fim.",
                                "textSignature": json.dumps({"phase": "commentary"}),
                            }
                        ],
                        "stopReason": "toolUse",
                    },
                },
            )
        )
        tap.put_nowait(
            _gateway_event(
                "agent.status",
                {
                    "runId": run_id,
                    "data": {"phase": "end"},
                },
            )
        )

    result_task = asyncio.create_task(
        client.send_chat_and_wait_text("prompt", timeout=0.5, idle_timeout=0.05)
    )
    producer_task = asyncio.create_task(emit_events())

    result = await result_task
    await producer_task

    assert result == "Vou continuar a apresentacao automaticamente ate ao fim."
