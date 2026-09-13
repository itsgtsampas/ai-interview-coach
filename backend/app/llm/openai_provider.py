"""Real OpenAI provider.

Not used by default (LLM_PROVIDER=stub).  Implemented against the HTTP API with
httpx so the project carries no extra SDK dependency.  Set LLM_PROVIDER=openai
and OPENAI_API_KEY to switch; no calling code changes.
"""

import json
from collections.abc import Iterator

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.exceptions import ProviderUnavailable
from app.llm.base import AgentStep, LLMResponse, RenderedPrompt, ToolSpec

_API = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ProviderUnavailable(
                "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
                "Set the key, or switch LLM_PROVIDER back to 'stub'."
            )
        self._key = settings.openai_api_key

    @staticmethod
    def _describe(response: httpx.Response) -> str:
        """The API's own error message, not just the status code.

        A 429 means "slow down" or "no credits remaining" — the status alone
        cannot tell them apart.
        """
        try:
            err = response.json().get("error", {}) or {}
        except ValueError:
            return f"HTTP {response.status_code}"
        code = err.get("code") or err.get("type") or f"HTTP {response.status_code}"
        message = err.get("message") or response.text[:200]
        return f"{code}: {message}"

    def _post(self, body: dict) -> dict:
        try:
            r = httpx.post(
                _API,
                json=body,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=60.0,
            )
        except httpx.HTTPError as exc:  # transport-level: DNS, TLS, timeout
            raise ProviderUnavailable(f"Could not reach OpenAI: {exc}") from exc

        if r.is_error:
            raise ProviderUnavailable(f"OpenAI rejected the request — {self._describe(r)}")
        return r.json()

    def complete_json(
        self,
        prompt: RenderedPrompt,
        schema: type[BaseModel],
        *,
        model: str,
        temperature: float,
    ) -> LLMResponse:
        data = self._post({
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            # json_object, not json_schema: Structured Outputs rejects most of
            # what Pydantic emits here (maxItems, minLength, default). The shape
            # is in the prompt's FORMAT block and structured.py validates it.
            "response_format": {"type": "json_object"},
        })
        usage = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    def stream_text(
        self,
        prompt: RenderedPrompt,
        *,
        model: str,
        temperature: float,
    ) -> Iterator[str]:
        """Stream tokens straight through to the caller.

        OpenAI speaks SSE too, so this re-frames one stream as ours. A frame
        that will not parse is skipped: a partial frame at a chunk boundary is
        normal, and `[DONE]` ends the stream.
        """
        body = {
            "model": model,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
        }
        try:
            with httpx.stream(
                "POST",
                _API,
                json=body,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=120.0,
            ) as response:
                if response.is_error:
                    response.read()  # the body is not loaded on a streamed response
                    raise ProviderUnavailable(
                        f"OpenAI rejected the stream — {self._describe(response)}"
                    )
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    piece = delta.get("content")
                    if piece:
                        yield piece
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"OpenAI stream failed: {exc}") from exc

    def plan_step(
        self, prompt: RenderedPrompt, tools: list[ToolSpec], history: list[AgentStep]
    ) -> AgentStep:
        messages = [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ]
        for step in history:
            if step.tool:
                messages.append({"role": "assistant", "content": f"Thought: {step.thought}"})
                messages.append({
                    "role": "user",
                    "content": f"Observation from {step.tool}: {step.observation}",
                })
        data = self._post({
            "model": get_settings().openai_chat_model_large,
            "temperature": 0.3,
            "messages": messages,
            "tools": [
                {"type": "function", "function": {
                    "name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ],
        })
        msg = data["choices"][0]["message"]
        usage = data.get("usage", {})
        used = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
        calls = msg.get("tool_calls") or []
        if calls:
            call = calls[0]["function"]
            return AgentStep(
                thought=msg.get("content") or f"Calling {call['name']}.",
                tool=call["name"],
                tool_input=json.loads(call.get("arguments") or "{}"),
                **used,
            )
        return AgentStep(thought="Answering from gathered context.",
                         final_answer=msg.get("content", ""), **used)
