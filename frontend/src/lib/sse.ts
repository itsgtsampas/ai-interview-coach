/** An SSE client built on fetch rather than EventSource.
 *
 *  EventSource can only issue GET and cannot set headers, which would put the
 *  bearer token in the query string — and so into logs and history. The cost is
 *  parsing the wire format here.
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

/** Split a buffer into complete frames, returning the unconsumed tail. */
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
      // Skip an unparseable frame; `done` still decides the outcome.
    }
  }
  return { frames, rest };
}

/** POST to an SSE endpoint and dispatch its events.
 *
 *  Resolves with the `done` payload. A stream that ends without one is a
 *  failure, whatever its status line said. */
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

  // Failures before the stream opens are ordinary HTTP.
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
          // Recorded, not thrown: cancelling mid-loop races with the last read.
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
