"""Server-Sent Events framing.

SSE rather than WebSocket: the flow is one-way and SSE is ordinary HTTP, so it
inherits the existing bearer auth, CORS and proxy configuration unchanged.

Four event names, which the client switches on:

    stage  {"key": "retrieving", "label": "Searching your CV"}
    token  {"text": "..."}            incremental prose
    done   {...}                      the final structured payload
    error  {"error": "...", "message": "..."}
"""

import json
from collections.abc import Iterator
from typing import Any

# Ignored by EventSource, but keeps idle proxies from closing the socket.
KEEPALIVE = ": keepalive\n\n"


def frame(event: str, data: Any) -> str:
    """One SSE event. `data:` may not contain a newline, hence no indent."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stage(key: str, label: str) -> str:
    return frame("stage", {"key": key, "label": label})


def token(text: str) -> str:
    return frame("token", {"text": text})


def done(payload: Any) -> str:
    return frame("done", payload)


def error(code: str, message: str, details: dict | None = None) -> str:
    return frame("error", {"error": code, "message": message, "details": details or {}})


SSE_HEADERS = {
    # Nginx buffers proxied responses by default, holding every token to the end.
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
}


def chunk_words(text: str, per_chunk: int = 3) -> Iterator[str]:
    """Split prose into small groups of words, whitespace preserved."""
    buffer: list[str] = []
    for piece in text.split(" "):
        buffer.append(piece)
        if len(buffer) >= per_chunk:
            yield " ".join(buffer) + " "
            buffer = []
    if buffer:
        yield " ".join(buffer)
