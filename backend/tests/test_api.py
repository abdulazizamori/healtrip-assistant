"""HTTP contract: validation, sessions, rate limits, no stack traces leaked."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

from .conftest import DB_URL, FakeLLM, call


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def new_session(client):
    return client.post("/api/sessions").json()["session_id"]


def test_health(client):
    body = client.get("/api/health").json()
    assert body["database"] is True and body["llm_configured"] is False


def test_chat_flow_with_fake_model(client):
    client.app.state.agent.llm = FakeLLM([[call("ask_clarifying_question",
                                                question="Which city are you in?", why_it_matters="search")]])
    r = client.post("/api/chat", json={"session_id": new_session(client), "message": "I need a cardiologist"})
    assert r.status_code == 200 and r.json()["type"] == "question"


def test_emergency_over_http(client):
    r = client.post("/api/chat", json={"session_id": new_session(client),
                                       "message": "chest pain and shortness of breath", "ui_language": "ar"})
    body = r.json()
    assert body["type"] == "emergency" and body["language"] == "en"  # replies in the patient's language


def test_unknown_session_is_404(client):
    r = client.post("/api/chat", json={"session_id": "00000000-0000-0000-0000-000000000000", "message": "hi"})
    assert r.status_code == 404


def test_too_long_message_is_rejected(client):
    r = client.post("/api/chat", json={"session_id": new_session(client), "message": "a" * 1500})
    assert r.status_code == 413


def test_bad_payload_is_422_without_internals(client):
    r = client.post("/api/chat", json={"session_id": "x", "message": "", "ui_language": "fr"})
    assert r.status_code == 422 and "Traceback" not in r.text


def test_rate_limit(client):
    from app.state import RateLimiter
    client.app.state.limiter = RateLimiter(2)
    codes = [client.post("/api/sessions").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
