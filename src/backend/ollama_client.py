"""Async streaming client for the Ollama API.

This module provides a thin wrapper around Ollama's /api/chat endpoint,
yielding content tokens as they arrive via NDJSON streaming.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .config import logger, settings


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


async def stream_chat(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream a chat completion from Ollama token-by-token.

    Args:
        messages: List of ``{"role": ..., "content": ...}`` dicts.

    Yields:
        Content token strings as they arrive.

    Raises:
        OllamaError: If the connection fails or Ollama returns an error.
    """
    url = f"{settings.ollama_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=5.0, pool=5.0),
        ) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise OllamaError(
                        f"Ollama returned {resp.status_code}: {body.decode(errors='replace')}"
                    )

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Ollama: non-JSON line: %s", line[:200])
                        continue

                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token

                    if data.get("done"):
                        return

    except httpx.ConnectError as exc:
        raise OllamaError(f"Cannot connect to Ollama at {settings.ollama_url}") from exc
    except httpx.ReadTimeout as exc:
        raise OllamaError("Ollama response timed out") from exc
    except OllamaError:
        raise
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama HTTP error: {exc}") from exc
