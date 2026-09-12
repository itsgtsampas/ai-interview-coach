"""Server-Sent Events framing.

SSE rather than WebSocket: everything here flows one way, server to browser,
and SSE is ordinary HTTP — it inherits the existing bearer auth, the CORS
config and the reverse proxy without any of them learning a second protocol.
A WebSocket would buy bidirectionality this application has no use for.

The wire format is four event names, and the client switches on them:

    stage  {"key": "retrieving", "label": "Searching your CV"}
    token  {"text": "..."}            incremental prose
    done   {...}                      the final structured payload
    error  {"error": "...", "message": "..."}
"""

import json
from collections.abc import Iterator
from typing import Any

# Comment frame. Proxies and load balancers close idle connections; a comment is
# ignored by EventSource but keeps the socket warm.
KEEPALIVE = ": keepalive\n\n"


def frame(event: str, data: Any) -> str:
    """One SSE event.

    `data:` may not contain a newline, so the JSON is dumped without indent and
    any embedded newline in a string value is already escaped by json.dumps.
    """
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
    # Nginx buffers proxied responses by default, which would hold every token
    # until the stream closed and defeat the entire point.
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
}


def chunk_words(text: str, per_chunk: int = 3) -> Iterator[str]:
    """Split prose into small groups of words, whitespace preserved.

    Used by providers that return a whole string at once so their output
    reaches the client through the same token events as a real stream.
    """
    buffer: list[str] = []
    for piece in text.split(" "):
        buffer.append(piece)
        if len(buffer) >= per_chunk:
            yield " ".join(buffer) + " "
            buffer = []
    if buffer:
        yield " ".join(buffer)
