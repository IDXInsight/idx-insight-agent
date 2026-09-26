"""Provider-neutral request/response types.

Provider adapters translate these to and from their own wire formats; nothing
provider-specific crosses this boundary.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "other"]


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema of the arguments object


class LLMToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any]


class LLMUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMRequest(BaseModel):
    # What the agent is deciding (e.g. "plan"); for logs and mocks, never sent.
    purpose: str
    messages: list[LLMMessage]
    # JSON Schema the reply must satisfy; mutually exclusive with ``tools``.
    response_schema: dict[str, Any] | None = None
    schema_name: str = "response"
    tools: list[LLMToolDefinition] = []
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _one_output_mode(self) -> LLMRequest:
        if self.response_schema is not None and self.tools:
            raise ValueError("a request uses either response_schema or tools, not both")
        return self


class LLMResponse(BaseModel):
    provider: str
    model: str
    text: str | None = None
    tool_calls: list[LLMToolCall] = []
    finish_reason: FinishReason = "other"
    usage: LLMUsage | None = None
