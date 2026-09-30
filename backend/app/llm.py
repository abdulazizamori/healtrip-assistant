"""LLM provider layer.

The agent talks to a tiny interface (`LLMClient.next_step`), not to Gemini directly:
  * the provider can be swapped (OpenAI, Claude, a local model) without touching agent logic;
  * tests run the whole agent with a scripted fake model — no network, no API key.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger("healtrip.llm")


class LLMUnavailable(Exception):
    """Provider down, timed out, rate-limited, or misconfigured. The agent turns this into a safe fallback."""


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str | None = None


@dataclass
class LLMStep:
    calls: list[ToolCall]
    raw: Any = None  # provider-native message, kept so it can be replayed verbatim (e.g. Gemini thought signatures)
    text: str = ""   # any free text the model produced (ignored: patients never see raw model text)


@dataclass
class Message:
    """Provider-neutral conversation history."""

    role: str                               # "user" | "model" | "tool"
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    results: list[tuple[ToolCall, dict]] = field(default_factory=list)
    raw: Any = None


class LLMClient(Protocol):
    def next_step(self, system: str, history: list[Message], tools: list[dict], allowed: list[str]) -> LLMStep: ...


# ====================================================================== Gemini

class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_s: float, retries: int):
        if not api_key:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        from google import genai
        from google.genai import types

        self._types = types
        self._model = model
        self._retries = retries
        self._client = genai.Client(api_key=api_key,
                                    http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def _contents(self, history: list[Message]) -> list:
        t = self._types
        out = []
        for m in history:
            if m.role == "user":
                # Patient text is wrapped and labelled as data; the system prompt says it is never an instruction.
                out.append(t.Content(role="user", parts=[t.Part(text=f"<patient_message>\n{m.text}\n</patient_message>")]))
            elif m.role == "model":
                out.append(m.raw if m.raw is not None else t.Content(role="model", parts=[
                    t.Part(function_call=t.FunctionCall(id=c.id, name=c.name, args=c.args)) for c in m.calls]))
            elif m.role == "tool":
                out.append(t.Content(role="user", parts=[
                    t.Part(function_response=t.FunctionResponse(id=c.id, name=c.name, response=r))
                    for c, r in m.results]))
        return out

    def next_step(self, system: str, history: list[Message], tools: list[dict], allowed: list[str]) -> LLMStep:
        t = self._types
        config = t.GenerateContentConfig(
            system_instruction=system,
            tools=[t.Tool(function_declarations=[t.FunctionDeclaration(**d) for d in tools])],
            # mode=ANY: the model MUST answer with a function call — it cannot write free text to the patient.
            # allowed_function_names lets the server take tools away (e.g. no more questions after the limit).
            tool_config=t.ToolConfig(function_calling_config=t.FunctionCallingConfig(
                mode=t.FunctionCallingConfigMode.ANY, allowed_function_names=allowed)),
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = self._contents(history)
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                resp = self._client.models.generate_content(model=self._model, contents=contents, config=config)
                calls = [ToolCall(name=fc.name, args=dict(fc.args or {}), id=fc.id) for fc in (resp.function_calls or [])]
                raw = resp.candidates[0].content if resp.candidates and resp.candidates[0].content else None
                return LLMStep(calls=calls, raw=raw, text=(resp.text or "") if not calls else "")
            except Exception as e:  # network, timeout, 429, 5xx, safety block…
                last_error = e
                log.warning("llm_call_failed", extra={"attempt": attempt + 1, "error_type": type(e).__name__})
        raise LLMUnavailable(type(last_error).__name__) from last_error
