"""LLM provider layer.

The agent talks to a tiny interface (`LLMClient.next_step`), not to a provider directly:
  * providers can be swapped or chained (Gemini first, Claude as the backup) without touching agent logic;
  * tests run the whole agent with a scripted fake model — no network, no API key.
"""

import json
import logging
import re
import time
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
    provider: str = ""  # which provider produced `raw`; another provider rebuilds the turn from `calls` instead


@dataclass
class Message:
    """Provider-neutral conversation history."""

    role: str                               # "user" | "model" | "tool"
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    results: list[tuple[ToolCall, dict]] = field(default_factory=list)
    raw: Any = None
    provider: str = ""


class LLMClient(Protocol):
    def next_step(self, system: str, history: list[Message], tools: list[dict], allowed: list[str]) -> LLMStep: ...


# ====================================================================== Gemini

# HTTP codes that mean "this model can't serve you right now" (quota / overload) rather than "your request is wrong"
_CAPACITY_CODES = {429, 503}


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout_s: float, retries: int,
                 fallback_models: list[str] | None = None, cooldown_s: float = 60.0):
        if not api_key:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        from google import genai
        from google.genai import types

        self._types = types
        # primary first; fallbacks are only used while a model ahead of them is out of quota or overloaded
        self._models = [model] + [m for m in (fallback_models or []) if m != model]
        self._cooldown_s = cooldown_s
        self._unavailable_until: dict[str, float] = {}
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
                # replay our own turns verbatim; a turn written by another provider is rebuilt from its calls
                out.append(m.raw if isinstance(m.raw, t.Content) else t.Content(role="model", parts=[
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
        attempt = 0
        while attempt <= self._retries:
            model = self._pick_model()
            try:
                resp = self._client.models.generate_content(model=model, contents=contents, config=config)
                calls = [ToolCall(name=fc.name, args=dict(fc.args or {}), id=fc.id) for fc in (resp.function_calls or [])]
                raw = resp.candidates[0].content if resp.candidates and resp.candidates[0].content else None
                return LLMStep(calls=calls, raw=raw, text=(resp.text or "") if not calls else "", provider="gemini")
            except Exception as e:  # network, timeout, 429, 5xx, safety block…
                last_error = e
                code = getattr(e, "code", None)
                log.warning("llm_call_failed", extra={"attempt": attempt + 1, "model": model,
                                                      "error_type": type(e).__name__, "status": code})
                if code in _CAPACITY_CODES and self._has_other_model(model):
                    # quota / overload: park this model and switch — this does not use up a retry
                    self._unavailable_until[model] = time.monotonic() + self._cooldown_s
                    log.warning("llm_model_cooldown", extra={"model": model, "seconds": self._cooldown_s})
                    continue
                attempt += 1
        raise LLMUnavailable(type(last_error).__name__) from last_error

    def _pick_model(self) -> str:
        now = time.monotonic()
        for m in self._models:
            if self._unavailable_until.get(m, 0) <= now:
                return m
        return self._models[-1]  # everything is cooling down: the last resort is still worth one try

    def _has_other_model(self, model: str) -> bool:
        now = time.monotonic()
        return any(m != model and self._unavailable_until.get(m, 0) <= now for m in self._models)


# ====================================================================== Claude

# Claude's strict tool mode rejects numeric/length/array-size constraints; the server re-checks all of them anyway
# (Pydantic models in tools.py), so they are only dropped from what Claude sees.
_UNSUPPORTED_IN_STRICT = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                          "minLength", "maxLength", "minItems", "maxItems"}
_TOOL_ID = re.compile(r"[^a-zA-Z0-9_-]")


def _strict_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        out = {k: _strict_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED_IN_STRICT}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    if isinstance(schema, list):
        return [_strict_schema(v) for v in schema]
    return schema


class ClaudeClient:
    """Anthropic Claude through the same interface.

    Claude Opus 5.5 does not accept a forced tool choice, so the "always answer with a tool" rule is carried by the
    system prompt (rule 6) with tool_choice=auto, and a reply without a tool call is caught by the agent exactly like
    Gemini's (counted as invalid output). Strict tools keep arguments schema-valid; the server still validates them.
    """

    def __init__(self, api_key: str, model: str, timeout_s: float, retries: int, effort: str = "low"):
        if not api_key:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
        import anthropic

        self._anthropic = anthropic
        self._model = model
        self._effort = effort
        # the SDK retries connection errors, 408, 409, 429 and 5xx with backoff
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=retries)

    def _tools(self, tools: list[dict], allowed: list[str]) -> list[dict]:
        # tools that are not allowed right now are simply not sent, so the model cannot call them
        return [{"name": d["name"], "description": d["description"], "strict": True,
                 "input_schema": _strict_schema(d["parameters_json_schema"])}
                for d in tools if d["name"] in allowed]

    def _messages(self, history: list[Message]) -> list[dict]:
        ids: dict[int, str] = {}

        def tool_id(c: ToolCall) -> str:
            # calls rebuilt from another provider may have no id (or one with characters Claude rejects)
            if id(c) not in ids:
                ids[id(c)] = _TOOL_ID.sub("_", c.id) if c.id else f"call_{len(ids)}"
            return ids[id(c)]

        out = []
        for m in history:
            if m.role == "user":
                out.append({"role": "user", "content": f"<patient_message>\n{m.text}\n</patient_message>"})
            elif m.role == "model":
                if m.provider == "anthropic" and m.raw is not None:
                    out.append({"role": "assistant", "content": m.raw})  # verbatim, thinking blocks included
                else:
                    out.append({"role": "assistant", "content": [
                        {"type": "tool_use", "id": tool_id(c), "name": c.name, "input": c.args} for c in m.calls]})
            elif m.role == "tool":
                out.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": tool_id(c), "is_error": "error" in r,
                     "content": json.dumps(r, ensure_ascii=False, default=str)}
                    for c, r in m.results]})
        return out

    def next_step(self, system: str, history: list[Message], tools: list[dict], allowed: list[str]) -> LLMStep:
        a = self._anthropic
        try:
            resp = self._client.beta.messages.create(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=self._messages(history),
                tools=self._tools(tools, allowed),
                tool_choice={"type": "auto"},
                output_config={"effort": self._effort},
                # if a safety classifier declines, Anthropic re-runs the request on its recommended fallback model
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except a.APIStatusError as e:
            log.warning("llm_call_failed", extra={"model": self._model, "error_type": type(e).__name__,
                                                  "status": e.status_code})
            raise LLMUnavailable(type(e).__name__) from e
        except a.APIError as e:  # connection error, timeout
            log.warning("llm_call_failed", extra={"model": self._model, "error_type": type(e).__name__})
            raise LLMUnavailable(type(e).__name__) from e

        if resp.stop_reason == "refusal":
            # every model in the fallback chain declined: retrying the same history will not help
            log.warning("llm_refusal", extra={"model": resp.model})
            raise LLMUnavailable("refusal")
        calls = [ToolCall(name=b.name, args=dict(b.input or {}), id=b.id) for b in resp.content if b.type == "tool_use"]
        text = "" if calls else "".join(b.text for b in resp.content if b.type == "text")
        return LLMStep(calls=calls, raw=resp.content, text=text, provider="anthropic")


# ====================================================================== provider chain

class FallbackLLM:
    """Tries providers in order. A provider that fails (LLMUnavailable) is skipped for `cooldown_s`.

    A turn stays on the provider that started it, so one turn never mixes two providers' native formats
    (thought signatures, tool-call ids); if that provider fails mid-turn, the next one takes over the rest.
    """

    def __init__(self, clients: list[tuple[str, LLMClient]], cooldown_s: float = 60.0):
        self._clients = clients
        self._cooldown_s = cooldown_s
        self._unavailable_until: dict[str, float] = {}

    def next_step(self, system: str, history: list[Message], tools: list[dict], allowed: list[str]) -> LLMStep:
        now = time.monotonic()
        ready = [c for c in self._clients if self._unavailable_until.get(c[0], 0) <= now]
        order = ready or self._clients  # all cooling down: still try, the alternative is a guaranteed fallback
        current = _turn_provider(history)
        order = sorted(order, key=lambda c: c[0] != current)  # stable: keeps priority otherwise

        last_error: Exception | None = None
        for name, client in order:
            try:
                return client.next_step(system, history, tools, allowed)
            except LLMUnavailable as e:
                last_error = e
                self._unavailable_until[name] = time.monotonic() + self._cooldown_s
                log.warning("llm_provider_unavailable", extra={"provider": name, "seconds": self._cooldown_s})
        raise LLMUnavailable(str(last_error)) from last_error


def _turn_provider(history: list[Message]) -> str:
    """Provider that produced the model steps after the latest patient message ('' if none yet)."""
    for m in reversed(history):
        if m.role == "user":
            return ""
        if m.role == "model" and m.provider:
            return m.provider
    return ""
