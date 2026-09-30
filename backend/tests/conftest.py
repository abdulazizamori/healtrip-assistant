import os

import pytest

from app.agent import Agent
from app.config import Settings
from app.db import Database, load_reference_data
from app.llm import LLMStep, LLMUnavailable, ToolCall
from app.state import SessionStore

DB_URL = os.environ.get("DATABASE_URL",
                        "postgresql://healtrip_agent_ro:readonly_dev_password@localhost:5432/healtrip")


class FakeLLM:
    """Scripted model. Each script item is a list of ToolCalls, an Exception to raise, or a callable(history)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.allowed_seen: list[list[str]] = []
        self.histories: list[list] = []

    def next_step(self, system, history, tools, allowed):
        self.calls += 1
        self.allowed_seen.append(list(allowed))
        self.histories.append(list(history))
        if not self.script:
            raise AssertionError("FakeLLM script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            item = item(history)
        return LLMStep(calls=item)


def call(name, **args):
    return ToolCall(name=name, args=args, id=f"{name}-{len(args)}")


@pytest.fixture(scope="session")
def db():
    d = Database(DB_URL)
    try:
        d.open()
    except Exception:
        pytest.skip("PostgreSQL not reachable (set DATABASE_URL)")
    yield d
    d.close()


@pytest.fixture(scope="session")
def ref(db):
    return load_reference_data(db)


@pytest.fixture
def settings():
    return Settings(gemini_api_key="", database_url=DB_URL)


@pytest.fixture
def make_agent(db, ref, settings):
    def _make(script):
        fake = FakeLLM(script)
        return Agent(fake, db, ref, settings), fake
    return _make


@pytest.fixture
def session():
    return SessionStore(60).create()


__all__ = ["FakeLLM", "call", "LLMUnavailable"]
