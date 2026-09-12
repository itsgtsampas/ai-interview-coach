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

    def _post(self, body: dict) -> dict:
        try:
            r = httpx.post(
                _API,
                json=body,
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=60.0,
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"OpenAI request failed: {exc}") from exc
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
            # json_object, not json_schema. Structured Outputs rejects most of
            # what Pydantic generates from our contracts - maxItems, minLength,
            # minimum, default, and objects without additionalProperties:false -
            # so passing model_json_schema() here 400s on the first request.
            #
            # This mode guarantees syntactically valid JSON and nothing more,
            # which is exactly the split the design already assumes: the shape is
            # described in the prompt's FORMAT block, and llm/structured.py
            # validates it against the Pydantic model with one repair retry.
            # That second line of defence exists precisely so the provider does
            # not have to be trusted with the schema.
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
        """Real token streaming, passed straight through to the caller.

        OpenAI speaks SSE on the wire too, so this parses one SSE stream and
        re-frames it as ours. `[DONE]` is the sentinel that ends it; a line that
        is not valid JSON after the `data: ` prefix is skipped rather than
        failing the response, because a half-written frame at a chunk boundary
        is normal.
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
                response.raise_for_status()
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
        calls = msg.get("tool_calls") or []
        if calls:
            call = calls[0]["function"]
            return AgentStep(
                thought=msg.get("content") or f"Calling {call['name']}.",
                tool=call["name"],
                tool_input=json.loads(call.get("arguments") or "{}"),
            )
        return AgentStep(thought="Answering from gathered context.",
                         final_answer=msg.get("content", ""))
