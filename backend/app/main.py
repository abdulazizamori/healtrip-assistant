"""HTTP layer. Endpoints:
  GET  /api/health     liveness + dependency status
  POST /api/sessions   create a conversation (server-generated id)
  POST /api/chat       one patient message -> one validated response
The agent's tools are NOT endpoints: they are internal functions only the agent can trigger.
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent import Agent
from .config import get_settings
from .db import Database, load_reference_data
from .llm import ClaudeClient, FallbackLLM, GeminiClient, LLMUnavailable
from .schemas import ChatRequest, ChatResponse, CreateSessionResponse
from .state import RateLimiter, SessionStore

_STD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message"}


class JsonFormatter(logging.Formatter):
    """Structured logs: event names + metadata. Never message content or anything identifying a patient."""

    def format(self, r: logging.LogRecord) -> str:
        extra = {k: v for k, v in r.__dict__.items() if k not in _STD}
        return json.dumps({"level": r.levelname, "logger": r.name, "event": r.getMessage(), **extra}, default=str)


def _setup_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)


log = logging.getLogger("healtrip.api")


def _build_llm(s):
    """Gemini first (with its own model fallbacks), Claude as the backup provider. Each is optional."""
    clients = []
    for name, make in (
        ("gemini", lambda: GeminiClient(s.gemini_api_key, s.gemini_model, s.llm_timeout_seconds, s.llm_retries,
                                        fallback_models=s.fallback_models)),
        ("anthropic", lambda: ClaudeClient(s.anthropic_api_key, s.claude_model, s.claude_timeout_seconds,
                                           s.llm_retries, effort=s.claude_effort)),
    ):
        try:
            clients.append((name, make()))
        except LLMUnavailable as e:
            log.warning("llm_provider_disabled", extra={"provider": name, "reason": str(e)})
    if not clients:
        log.error("llm_disabled")
        return None  # the API still runs: red-flag rules and safe fallbacks keep working
    return clients[0][1] if len(clients) == 1 else FallbackLLM(clients)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    s = get_settings()
    db = Database(s.database_url)
    db.open()
    ref = load_reference_data(db)
    llm = _build_llm(s)
    app.state.db = db
    app.state.agent = Agent(llm, db, ref, s)
    app.state.sessions = SessionStore(s.session_ttl_minutes)
    app.state.limiter = RateLimiter(s.rate_limit_per_minute)
    log.info("startup", extra={"model": s.gemini_model, "fallback_models": s.fallback_models,
                               "claude_model": s.claude_model if s.anthropic_api_key else None,
                               "llm_enabled": llm is not None,
                               "cities": len(ref.cities), "specialties": len(ref.specialties)})
    yield
    db.close()


app = FastAPI(title="HealTrip Patient Decision Assistant", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "invalid_request",
                                                  "details": [e["msg"] for e in exc.errors()][:5]})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled_error")  # full trace in logs, never in the response
    return JSONResponse(status_code=500, content={"error": "internal_error"})


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.get("/api/health")
def health(request: Request):
    agent: Agent = request.app.state.agent
    db_ok = request.app.state.db.ping()
    return JSONResponse(status_code=200 if db_ok else 503,
                        content={"status": "ok" if db_ok else "degraded", "database": db_ok,
                                 "llm_configured": agent.llm is not None})


@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session(request: Request):
    if not request.app.state.limiter.allow(_client_key(request)):
        raise HTTPException(429, "too_many_requests")
    return CreateSessionResponse(session_id=request.app.state.sessions.create().id)


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request):
    s = get_settings()
    if not request.app.state.limiter.allow(_client_key(request)):
        raise HTTPException(429, "too_many_requests")
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "empty_message")
    if len(message) > s.max_message_chars:
        raise HTTPException(413, f"message_too_long (max {s.max_message_chars} characters)")

    session = request.app.state.sessions.get(body.session_id)
    if session is None:
        raise HTTPException(404, "session_not_found")  # frontend starts a new session
    if session.user_turns >= s.max_user_turns_per_session:
        raise HTTPException(409, "session_turn_limit")
    if not session.lock.acquire(blocking=False):
        raise HTTPException(409, "turn_in_progress")  # one turn at a time per session
    try:
        return request.app.state.agent.handle_turn(session, message, body.ui_language)
    finally:
        session.lock.release()
