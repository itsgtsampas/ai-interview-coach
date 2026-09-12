/** A Server-Sent Events client built on fetch rather than EventSource.
 *
 *  EventSource is the obvious choice and the wrong one here: it can only issue
 *  GET, and it cannot set headers — so the bearer token would have to travel in
 *  the query string, which lands in server logs and browser history. Reading the
 *  stream off a normal fetch keeps the Authorization header and lets these be
 *  POSTs, at the cost of parsing the (very small) wire format ourselves.
 */

import { ApiError, token } from "../api/client";

export interface SseHandlers<T> {
  /** A named step of the pipeline started. */
  onStage?: (key: string, label: string) => void;
  /** A piece of prose arrived. Append it; do not replace. */
  onToken?: (text: string) => void;
  /** The stream finished with its payload. */
  onDone?: (payload: T) => void;
}

interface Frame {
  event: string;
  data: unknown;
}

/** Split a decoded buffer into complete frames, returning the unconsumed tail.
 *
 *  A chunk boundary can fall anywhere, including mid-frame, so anything after
 *  the last blank line is carried forward rather than parsed. */
function drain(buffer: string): { frames: Frame[]; rest: string } {
  const frames: Frame[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";

  for (const block of parts) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue; // keepalive comment
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (!data.length) continue;
    try {
      frames.push({ event, data: JSON.parse(data.join("\n")) });
    } catch {
      // A frame we cannot parse is a bug on the server, not something to show
      // the user mid-stream; the stream continues and `done` still decides.
    }
  }
  return { frames, rest };
}

/**
 * POST to an SSE endpoint and dispatch its events.
 *
 * Resolves with the `done` payload. Rejects if the request fails, if the server
 * sends an `error` event, or if the stream ends without a `done` — a stream that
 * stops early is a failure even though its status line said 200.
 */
export async function streamRequest<T>(
  path: string,
  body: unknown,
  handlers: SseHandlers<T> = {},
  signal?: AbortSignal,
): Promise<T> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const t = token.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);

  const response = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });

  // Failures before the stream opens are ordinary HTTP, so they keep the
  // ordinary error shape and the ordinary handling.
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) token.clear();
    throw new ApiError(
      response.status,
      payload.error ?? "stream_failed",
      payload.message ?? "The request failed before it started.",
      payload.details ?? {},
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: T | undefined;
  let failure: ApiError | undefined;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = drain(buffer);
      buffer = rest;

      for (const frame of frames) {
        if (frame.event === "stage") {
          const stage = frame.data as { key: string; label: string };
          handlers.onStage?.(stage.key, stage.label);
        } else if (frame.event === "token") {
          handlers.onToken?.((frame.data as { text: string }).text);
        } else if (frame.event === "done") {
          result = frame.data as T;
          handlers.onDone?.(result);
        } else if (frame.event === "error") {
          const e = frame.data as { error: string; message: string; details?: object };
          // Recorded rather than thrown: the stream is still open, and cancelling
          // the reader from inside the loop races with the last read.
          failure = new ApiError(200, e.error, e.message, e.details ?? {});
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (failure) throw failure;
  if (result === undefined) {
    throw new ApiError(
      200,
      "stream_incomplete",
      "The connection closed before the result arrived. Try again.",
    );
  }
  return result;
}
