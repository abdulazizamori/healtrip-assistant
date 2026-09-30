"""Tools the agent can call.

Two kinds:
  * DATA tools (read-only lookups). Their arguments are validated in code before any query runs.
    They return IDs + attributes, but NOT names/phones/addresses — the model has nothing real
    to copy into its text, so any name it wrote would be invented and is caught by output validation.
  * TERMINAL tools. The model cannot write free text to the patient; its turn ends only by calling
    `ask_clarifying_question` or `submit_recommendation`, and both are validated before anything
    reaches the user.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from .db import (DOCTOR_SLOTS_SQL, EMERGENCY_HOSPITALS_SQL, SEARCH_DOCTORS_SQL, Database,
                 ReferenceData)
from .schemas import NextStep

MAX_RESULTS = 5
DATA_TOOLS = {"search_doctors", "find_emergency_hospitals", "get_doctor_availability"}
ASK = "ask_clarifying_question"
SUBMIT = "submit_recommendation"
TERMINAL_TOOLS = {ASK, SUBMIT}


class ToolInputError(ValueError):
    """Raised when the model sends invalid arguments. The message is returned to the model so it can fix them."""


# ====================================================================== schemas shown to the model

def build_tool_schemas(ref: ReferenceData) -> list[dict]:
    """JSON-schema function declarations. Enums come from the DB, so the model sees only real values."""
    cities, specialties, languages = sorted(ref.cities), sorted(ref.specialties), sorted(ref.languages)
    return [
        {
            "name": "search_doctors",
            "description": ("Search active doctors in the HealTrip database. Returns at most 5 matches as IDs and "
                            "attributes. Call this before recommending any doctor. Empty result means no match."),
            "parameters_json_schema": {
                "type": "object",
                "properties": {
                    "specialty": {"type": "string", "enum": specialties},
                    "city": {"type": "string", "enum": cities},
                    "language": {"type": "string", "enum": languages,
                                 "description": "Only doctors who speak this language (optional)."},
                    "accepts_second_opinion": {"type": "boolean",
                                               "description": "Set true when the patient wants a second opinion."},
                    "teleconsult": {"type": "boolean", "description": "Only doctors offering video consultations."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTS},
                },
                "required": ["specialty", "city"],
            },
        },
        {
            "name": "find_emergency_hospitals",
            "description": "List hospitals with an emergency department in a city (IDs only).",
            "parameters_json_schema": {
                "type": "object",
                "properties": {"city": {"type": "string", "enum": cities}},
                "required": ["city"],
            },
        },
        {
            "name": "get_doctor_availability",
            "description": "Next 3 open appointment slots for a doctor ID returned by search_doctors.",
            "parameters_json_schema": {
                "type": "object",
                "properties": {"doctor_id": {"type": "integer"}},
                "required": ["doctor_id"],
            },
        },
        {
            "name": ASK,
            "description": ("Ask the patient ONE short clarifying question. Only ask when the answer would change "
                            "the recommended next step. Ends your turn."),
            "parameters_json_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "One question, in the patient's language."},
                    "why_it_matters": {"type": "string", "description": "Internal note: how the answer changes the decision."},
                },
                "required": ["question", "why_it_matters"],
            },
        },
        {
            "name": SUBMIT,
            "description": ("Submit the final next-step recommendation. doctor_ids / hospital_ids must come from "
                            "tool results in this conversation. Ends your turn."),
            "parameters_json_schema": {
                "type": "object",
                "properties": {
                    "next_step": {"type": "string", "enum": [s.value for s in NextStep]},
                    "urgency": {"type": "string", "enum": ["routine", "soon", "urgent", "emergency"]},
                    "specialty": {"type": "string", "enum": specialties,
                                  "description": "Required for SPECIALIST and SECOND_OPINION."},
                    "doctor_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": MAX_RESULTS},
                    "hospital_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 3},
                    "patient_message": {"type": "string",
                                        "description": ("Short explanation for the patient in their language. "
                                                        "Do NOT write doctor names, hospital names, phone numbers or "
                                                        "addresses — the app shows those as cards from the database.")},
                    "reasoning": {"type": "string", "description": "Internal note for audit logs. Not shown."},
                },
                "required": ["next_step", "urgency", "patient_message", "reasoning"],
            },
        },
    ]


# ====================================================================== input validation (data tools)

class _Strict(BaseModel):
    model_config = {"extra": "forbid"}  # unknown arguments are rejected, not ignored


def _in(value: str | None, allowed: dict, field: str) -> str | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v not in allowed:
        raise ValueError(f"unknown {field} '{value}'. Allowed: {sorted(allowed)}")
    return v


class SearchDoctorsInput(_Strict):
    specialty: str
    city: str
    language: str | None = None
    accepts_second_opinion: bool = False
    teleconsult: bool = False
    limit: int = Field(default=MAX_RESULTS, ge=1, le=MAX_RESULTS)


class EmergencyInput(_Strict):
    city: str


class AvailabilityInput(_Strict):
    doctor_id: int = Field(ge=1)


class ToolContext:
    """What a tool is allowed to know. Identity/session come from the server — never from model arguments."""

    def __init__(self, db: Database, ref: ReferenceData):
        self.db, self.ref = db, ref


def run_data_tool(name: str, args: dict, ctx: ToolContext) -> dict:
    try:
        if name == "search_doctors":
            a = SearchDoctorsInput(**args)
            params = {
                "specialty": _in(a.specialty, ctx.ref.specialties, "specialty"),
                "city": _in(a.city, ctx.ref.cities, "city"),
                "language": _in(a.language, ctx.ref.languages, "language"),
                "second_opinion": a.accepts_second_opinion,
                "teleconsult": a.teleconsult,
                "limit": a.limit,
            }
            rows = ctx.db.fetch_all(SEARCH_DOCTORS_SQL, params)
            return {"count": len(rows), "doctors": [_doctor_for_model(r) for r in rows]}

        if name == "find_emergency_hospitals":
            a = EmergencyInput(**args)
            rows = ctx.db.fetch_all(EMERGENCY_HOSPITALS_SQL, {"city": _in(a.city, ctx.ref.cities, "city")})
            return {"count": len(rows), "hospitals": [{"hospital_id": r["id"], "city": r["city_code"],
                                                       "has_emergency": True} for r in rows]}

        if name == "get_doctor_availability":
            a = AvailabilityInput(**args)
            rows = ctx.db.fetch_all(DOCTOR_SLOTS_SQL, {"doctor_id": a.doctor_id})
            return {"doctor_id": a.doctor_id, "open_slots": [r["starts_at"].isoformat() for r in rows]}

    except ValidationError as e:
        raise ToolInputError(_short_errors(e)) from e
    except ValueError as e:
        raise ToolInputError(str(e)) from e
    raise ToolInputError(f"unknown tool '{name}'")


def _doctor_for_model(r: dict) -> dict:
    # Deliberately no name / phone / address: the model reasons over attributes and IDs only.
    return {
        "doctor_id": r["id"],
        "specialty": r["specialty_code"],
        "hospital_id": r["hospital_id"],
        "city": r["city_code"],
        "languages": list(r["languages"]),
        "years_experience": r["years_experience"],
        "accepts_second_opinion": r["accepts_second_opinion"],
        "offers_teleconsult": r["offers_teleconsult"],
        "next_available": r["next_available"].isoformat() if isinstance(r["next_available"], datetime) else None,
    }


def _short_errors(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, err['loc'])) or 'input'}: {err['msg']}" for err in e.errors()[:5])


# ====================================================================== terminal tools (model output)

# Things the model must never put in free text: they could only be invented.
_FORBIDDEN_IN_TEXT = [
    (re.compile(r"\bdr\.?\s+[A-Z]", re.I), "doctor names"),
    (re.compile(r"\bdoctor\s+[A-Z][a-z]+", 0), "doctor names"),
    (re.compile(r"(^|\s)د\.\s*\S"), "doctor names"),
    (re.compile(r"\+?\d[\d\s\-]{7,}\d"), "phone numbers"),
    (re.compile(r"https?://|www\.", re.I), "links"),
]


def _check_free_text(text: str) -> str:
    for pattern, what in _FORBIDDEN_IN_TEXT:
        if pattern.search(text):
            raise ValueError(f"patient-facing text must not contain {what}; the app renders those from the database")
    return text.strip()


class ClarifyingQuestion(_Strict):
    question: str = Field(min_length=3, max_length=300)
    why_it_matters: str = Field(max_length=500)

    @field_validator("question")
    @classmethod
    def one_question(cls, v: str) -> str:
        v = _check_free_text(v)
        if v.count("?") + v.count("؟") > 2:
            raise ValueError("ask ONE question at a time")
        return v


class Recommendation(_Strict):
    next_step: NextStep
    urgency: Literal["routine", "soon", "urgent", "emergency"]
    specialty: str | None = None
    doctor_ids: list[int] = Field(default_factory=list, max_length=MAX_RESULTS)
    hospital_ids: list[int] = Field(default_factory=list, max_length=3)
    patient_message: str = Field(min_length=10, max_length=900)
    reasoning: str = Field(max_length=1500)

    @field_validator("patient_message")
    @classmethod
    def no_invented_facts(cls, v: str) -> str:
        return _check_free_text(v)

    @model_validator(mode="after")
    def consistent(self):
        if self.next_step in (NextStep.SPECIALIST, NextStep.SECOND_OPINION) and not self.specialty:
            raise ValueError(f"specialty is required for {self.next_step.value}")
        if self.next_step == NextStep.EMERGENCY:
            if self.doctor_ids:
                raise ValueError("EMERGENCY must not list doctors; list emergency hospital_ids instead")
            if self.urgency != "emergency":
                raise ValueError("EMERGENCY requires urgency='emergency'")
        return self


def validate_recommendation(args: dict, seen_doctor_ids: set[int], seen_hospital_ids: set[int],
                            ref: ReferenceData) -> Recommendation:
    """Grounding check: every ID must have been returned by a tool in THIS session."""
    try:
        rec = Recommendation(**args)
    except ValidationError as e:
        raise ToolInputError(_short_errors(e)) from e
    if rec.specialty is not None:
        rec.specialty = _in(rec.specialty, ref.specialties, "specialty")  # type: ignore[assignment]
    unknown_docs = [i for i in rec.doctor_ids if i not in seen_doctor_ids]
    unknown_hosp = [i for i in rec.hospital_ids if i not in seen_hospital_ids]
    if unknown_docs or unknown_hosp:
        raise ToolInputError(
            f"IDs not returned by any tool in this conversation: doctors={unknown_docs} hospitals={unknown_hosp}. "
            "Only recommend IDs from search results. If nothing matched, say so and recommend no doctors.")
    return rec


def validate_question(args: dict) -> ClarifyingQuestion:
    try:
        return ClarifyingQuestion(**args)
    except ValidationError as e:
        raise ToolInputError(_short_errors(e)) from e


def check_against_db(rec: Recommendation, doctor_rows: list[dict], hospital_rows: list[dict]) -> None:
    """Semantic checks on the hydrated rows: the IDs are real, but do they fit the decision?"""
    if len(doctor_rows) != len(set(rec.doctor_ids)) or len(hospital_rows) != len(set(rec.hospital_ids)):
        raise ToolInputError("some IDs no longer exist or are inactive; search again")
    for d in doctor_rows:
        if rec.specialty and d["specialty_code"] != rec.specialty:
            raise ToolInputError(f"doctor {d['id']} is {d['specialty_code']}, not {rec.specialty}")
        if rec.next_step == NextStep.SECOND_OPINION and not d["accepts_second_opinion"]:
            raise ToolInputError(f"doctor {d['id']} does not accept second-opinion requests")
    if rec.next_step == NextStep.EMERGENCY:
        for h in hospital_rows:
            if not h["has_emergency"]:
                raise ToolInputError(f"hospital {h['id']} has no emergency department")
