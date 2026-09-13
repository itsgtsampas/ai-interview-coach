"""Provider-agnostic LLM contracts.

Every prompt is fully rendered to text (`system` + `user`) so it can be
inspected, versioned and shown in the documentation.  `payload` carries the same
information in structured form: real providers ignore it, the deterministic stub
provider consumes it.  Swapping providers changes no calling code.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass
class RenderedPrompt:
    stage: str
    version: str
    system: str
    user: str
    payload: dict[str, Any] = field(default_factory=dict)

    def cache_key_material(self) -> str:
        return f"{self.stage}|{self.version}|{self.system}|{self.user}"


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class AgentStep:
    """One iteration of the ReAct loop: a thought plus either a tool call or the answer."""

    thought: str
    tool: str | None = None
    tool_input: dict[str, Any] | None = None
    observation: str | None = None
    final_answer: str | None = None
    # Usage for this single iteration. The agent loop is the one stage that does
    # not go through complete_structured, so without these its cost is invisible.
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMProvider(Protocol):
    name: str

    def complete_json(
        self,
        prompt: RenderedPrompt,
        schema: type[BaseModel],
        *,
        model: str,
        temperature: float,
    ) -> LLMResponse: ...

    def stream_text(
        self,
        prompt: RenderedPrompt,
        *,
        model: str,
        temperature: float,
    ) -> Iterator[str]:
        """Yield a prose answer in pieces, for stages rendered as they arrive.

        Only prose stages implement this. Structured stages stay on
        `complete_json`, because a half-parsed JSON object is not something a
        user interface can render — progress for those is reported as stage
        events instead of partial output.
        """
        ...

    def plan_step(
        self,
        prompt: RenderedPrompt,
        tools: list[ToolSpec],
        history: list[AgentStep],
    ) -> AgentStep: ...
