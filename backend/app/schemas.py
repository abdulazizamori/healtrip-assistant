"""Public API contracts (what the frontend sends and receives)."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NextStep(str, Enum):
    """The closed set of decisions the assistant may make. It never diagnoses."""

    EMERGENCY = "EMERGENCY"                         # go to the ER / call emergency services now
    SPECIALIST = "SPECIALIST"                       # book a specialist
    SECOND_OPINION = "SECOND_OPINION"               # already has a diagnosis/plan, wants another view
    GENERAL_PRACTITIONER = "GENERAL_PRACTITIONER"   # start with a GP / internal medicine


class ResponseType(str, Enum):
    QUESTION = "question"               # clarifying question
    RECOMMENDATION = "recommendation"   # a next step (+ options from the DB)
    EMERGENCY = "emergency"             # red flag: stop and seek emergency care
    ERROR = "error"                     # safe fallback, something failed


class CreateSessionResponse(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    # max length is enforced again in the handler from settings; this is a hard ceiling
    message: str = Field(min_length=1, max_length=4000)
    ui_language: Literal["ar", "en"] = "en"


class LocalizedName(BaseModel):
    code: str
    name_en: str
    name_ar: str


class HospitalCard(BaseModel):
    id: int
    name_en: str
    name_ar: str
    address_en: str
    address_ar: str
    phone: str
    has_emergency: bool
    city: LocalizedName


class DoctorCard(BaseModel):
    id: int
    name_en: str
    name_ar: str
    specialty: LocalizedName
    hospital_id: int
    hospital_en: str
    hospital_ar: str
    city: LocalizedName
    languages: list[str]
    years_experience: int
    accepts_second_opinion: bool
    offers_teleconsult: bool
    next_available: datetime | None


class ChatResponse(BaseModel):
    session_id: str
    type: ResponseType
    message: str                       # text shown in the chat bubble
    language: Literal["ar", "en"]      # language of `message`
    next_step: NextStep | None = None
    urgency: Literal["routine", "soon", "urgent", "emergency"] | None = None
    specialty: LocalizedName | None = None
    doctors: list[DoctorCard] = []     # ALWAYS hydrated from the DB, never from LLM text
    hospitals: list[HospitalCard] = []
    disclaimer: bool = True
