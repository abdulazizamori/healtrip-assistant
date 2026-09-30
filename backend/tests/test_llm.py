"""GeminiClient model fallback: quota/overload moves to the next model; other errors use the normal retry budget."""

from types import SimpleNamespace

import pytest

from app.llm import GeminiClient, LLMUnavailable, Message


class ApiErr(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def _ok():
    fc = SimpleNamespace(name="ask_clarifying_question", args={"question": "?"}, id="1")
    return SimpleNamespace(function_calls=[fc], candidates=[], text="")


class FakeModels:
    def __init__(self, script):
        self.script = dict(script)  # model -> list of results/exceptions
        self.used: list[str] = []

    def generate_content(self, model, contents, config):
        self.used.append(model)
        item = self.script[model].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(script, fallbacks, retries=1):
    pytest.importorskip("google.genai")
    c = GeminiClient("test-key", "primary", timeout_s=5, retries=retries, fallback_models=fallbacks)
    c._client = SimpleNamespace(models=FakeModels(script))
    return c


def _call(c):
    return c.next_step("sys", [Message(role="user", text="hi")], tools=[], allowed=["ask_clarifying_question"])


def test_quota_error_switches_to_fallback_and_stays_there():
    c = _client({"primary": [ApiErr(429)], "backup": [_ok(), _ok()]}, ["backup"])
    assert _call(c).calls[0].name == "ask_clarifying_question"
    _call(c)  # primary is cooling down: goes straight to the backup
    assert c._client.models.used == ["primary", "backup", "backup"]


def test_overload_switches_without_using_a_retry():
    c = _client({"primary": [ApiErr(503)], "backup": [ApiErr(500), _ok()]}, ["backup"], retries=1)
    _call(c)  # 503 switches models for free; the 500 on the backup uses the one retry
    assert c._client.models.used == ["primary", "backup", "backup"]


def test_non_capacity_error_does_not_switch_models():
    c = _client({"primary": [ApiErr(400), ApiErr(400)], "backup": [_ok()]}, ["backup"], retries=1)
    with pytest.raises(LLMUnavailable):
        _call(c)
    assert c._client.models.used == ["primary", "primary"]


def test_all_models_out_of_quota_raises():
    c = _client({"primary": [ApiErr(429)], "backup": [ApiErr(429), ApiErr(429)]}, ["backup"], retries=1)
    with pytest.raises(LLMUnavailable):
        _call(c)


# ====================================================================== Claude client

from app.llm import ClaudeClient, FallbackLLM, LLMStep, ToolCall  # noqa: E402

TOOLS = [
    {"name": "search_doctors", "description": "d",
     "parameters_json_schema": {"type": "object", "required": ["city"], "properties": {
         "city": {"type": "string", "enum": ["jeddah"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5}}}},
    {"name": "ask_clarifying_question", "description": "q",
     "parameters_json_schema": {"type": "object", "required": ["question"],
                                "properties": {"question": {"type": "string"}}}},
]


class FakeMessages:
    def __init__(self, result):
        self.result, self.kwargs = result, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _claude(result):
    pytest.importorskip("anthropic")
    c = ClaudeClient("test-key", "claude-opus-5-5", timeout_s=5, retries=0)
    c._client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(result)))
    return c


def _resp(*blocks, stop_reason="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, model="claude-opus-5-5")


def test_claude_parses_tool_calls_and_sends_only_allowed_strict_tools():
    block = SimpleNamespace(type="tool_use", name="search_doctors", input={"city": "jeddah"}, id="toolu_1")
    c = _claude(_resp(block))
    step = _call_with(c, allowed=["search_doctors"])
    assert step.calls == [ToolCall(name="search_doctors", args={"city": "jeddah"}, id="toolu_1")]
    assert step.provider == "anthropic"
    sent = c._client.beta.messages.kwargs
    assert [t["name"] for t in sent["tools"]] == ["search_doctors"]  # the other tool is not offered at all
    schema = sent["tools"][0]["input_schema"]
    assert sent["tools"][0]["strict"] and schema["additionalProperties"] is False
    assert "maximum" not in schema["properties"]["limit"]  # unsupported in strict mode; the server re-validates
    assert sent["tool_choice"] == {"type": "auto"}  # forced tool choice is rejected by this model


def _call_with(c, allowed, history=None):
    return c.next_step("sys", history or [Message(role="user", text="hi")], TOOLS, allowed)


def test_claude_rebuilds_turns_from_other_providers_with_matching_ids():
    call = ToolCall(name="search_doctors", args={"city": "jeddah"}, id=None)  # e.g. a Gemini call without an id
    history = [Message(role="user", text="chest pain"),
               Message(role="model", calls=[call], raw=object(), provider="gemini"),
               Message(role="tool", results=[(call, {"count": 0, "doctors": []})])]
    c = _claude(_resp(SimpleNamespace(type="tool_use", name="ask_clarifying_question",
                                      input={"question": "?"}, id="toolu_2")))
    _call_with(c, allowed=["ask_clarifying_question"], history=history)
    user, model, tool = c._client.beta.messages.kwargs["messages"]
    assert "<patient_message>" in user["content"]
    assert model["content"][0]["id"] == tool["content"][0]["tool_use_id"]  # Gemini's raw is never sent to Claude


def test_claude_refusal_and_api_errors_become_llm_unavailable():
    with pytest.raises(LLMUnavailable):
        _call_with(_claude(_resp(stop_reason="refusal")), allowed=["ask_clarifying_question"])
    import anthropic
    with pytest.raises(LLMUnavailable):
        _call_with(_claude(anthropic.APIConnectionError(request=None)), allowed=["ask_clarifying_question"])


# ====================================================================== provider chain

class Scripted:
    def __init__(self, name, results):
        self.name, self.results, self.calls = name, list(results), 0

    def next_step(self, *a):
        self.calls += 1
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return LLMStep(calls=[ToolCall(name="ask_clarifying_question", args={})], provider=self.name)


def test_chain_moves_to_backup_and_parks_the_failed_provider():
    g, a = Scripted("gemini", [LLMUnavailable("quota")]), Scripted("anthropic", [None, None])
    chain = FallbackLLM([("gemini", g), ("anthropic", a)])
    hist = [Message(role="user", text="hi")]
    assert chain.next_step("s", hist, [], []).provider == "anthropic"
    chain.next_step("s", hist, [], [])  # gemini is cooling down: not even tried
    assert (g.calls, a.calls) == (1, 2)


def test_chain_keeps_a_turn_on_the_provider_that_started_it():
    g, a = Scripted("gemini", [None]), Scripted("anthropic", [None])
    chain = FallbackLLM([("gemini", g), ("anthropic", a)])
    hist = [Message(role="user", text="hi"), Message(role="model", provider="anthropic"), Message(role="tool")]
    assert chain.next_step("s", hist, [], []).provider == "anthropic"
    assert g.calls == 0


def test_chain_raises_when_every_provider_fails():
    chain = FallbackLLM([("gemini", Scripted("gemini", [LLMUnavailable("x")])),
                         ("anthropic", Scripted("anthropic", [LLMUnavailable("y")]))])
    with pytest.raises(LLMUnavailable):
        chain.next_step("s", [Message(role="user", text="hi")], [], [])
