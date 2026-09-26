"""Structured output: schema generation and strict validation of replies.

Validation happens here, outside any provider, so every provider is held to the
same contract. Malformed output raises; it is never coerced or partially used.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from idx_insight.llm.errors import LLMStructuredOutputError
from idx_insight.llm.types import LLMResponse

M = TypeVar("M", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema accepted by strict structured-output modes.

    Strict modes require every property to be listed as required and objects to
    forbid additional properties. ``$defs`` are inlined and titles/defaults
    dropped to stay within the schema subset providers document.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return clean(defs[node["$ref"].split("/")[-1]])
        out = {k: clean(v) for k, v in node.items() if k not in ("title", "default")}
        if out.get("type") == "object":
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out

    return clean(schema)


def parse_json_object(text: str | None) -> dict[str, Any]:
    if not text or not text.strip():
        raise LLMStructuredOutputError("empty reply where JSON was required")
    body = text.strip()
    if match := _FENCE.match(body):
        body = match.group(1)
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMStructuredOutputError(f"reply is not valid JSON ({exc.msg})") from None
    if not isinstance(value, dict):
        raise LLMStructuredOutputError("reply JSON is not an object")
    return value


def validate_payload(payload: dict[str, Any], model: type[M]) -> M:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "<root>"
        raise LLMStructuredOutputError(
            f"reply does not match schema at '{where}': {first['msg']}") from None


def parse_structured(response: LLMResponse, model: type[M]) -> M:
    if response.finish_reason == "length":
        raise LLMStructuredOutputError("reply was truncated by the output limit")
    return validate_payload(parse_json_object(response.text), model)
