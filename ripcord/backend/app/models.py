"""
Shared data models for Ripcord.

These mirror the objects used across the pipeline (entity_detector output,
risk_engine output, clarification_engine output) and are what the session
WebSocket sends to the dashboard.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Word(BaseModel):
    """One word from an AssemblyAI Turn message (or any ASR with word confidences)."""

    text: str
    confidence: float
    start: int = 0
    end: int = 0
    word_is_final: bool = True


class EntityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNCERTAIN = "UNCERTAIN"
    CLARIFYING = "CLARIFYING"
    VERIFIED = "VERIFIED"
    INVALIDATED = "INVALIDATED"


class CriticalEntity(BaseModel):
    """Output of entity_detector.py — a candidate critical numeric entity."""

    type: str = "order_id"
    value: str
    raw_words: list[Word] = Field(default_factory=list)
    confidence: float
    expected_pattern: str = r"\d{4}"
    format_valid: bool = True
    status: EntityStatus = EntityStatus.UNKNOWN
    turn_order: int = 0
    end_of_turn_confidence: Optional[float] = None

    # --- v2: richer evidence about HOW the number was heard -----------------
    # One confidence per digit of `value` (a digit inherits the confidence of
    # the word(s) it was spoken with). Drives the per-digit view in the UI.
    digit_confidences: list[float] = Field(default_factory=list)
    # How the caller said it: "digits" (one five eight zero), "pairs"
    # (fifteen eighty) or "cardinal" (one thousand five hundred eighty).
    style: Literal["digits", "pairs", "cardinal", "numeral"] = "digits"
    min_confidence: float = 1.0
    low_conf_fraction: float = 0.0
    context_confidence: Optional[float] = None  # mean confidence of the words around the number
    teen_ten_words: int = 0  # fifteen/fifty-type words — a classic ASR confusion
    homophone_digits: int = 0  # "to", "for", "won", "ate" read as digits
    carrier_found: bool = True
    competing_spans: int = 0  # other number-like spans in the same turn
    speech_rate: Optional[float] = None  # digits per second, when timestamps exist


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskAssessment(BaseModel):
    """Output of risk_engine.py."""

    risk_score: float  # estimated probability that the captured value is wrong
    risk_level: RiskLevel
    signals: list[str] = Field(default_factory=list)
    should_clarify: bool
    # Per-feature contribution to the log-odds of "wrong" (positive = riskier).
    breakdown: dict[str, float] = Field(default_factory=dict)
    # Human-readable reasons, strongest first.
    reasons: list[str] = Field(default_factory=list)
    # 0-based digit positions Ripcord is least sure about.
    weak_positions: list[int] = Field(default_factory=list)
    threshold: float = 0.35
    engine: str = "learned-v2"


class ClarificationQuestion(BaseModel):
    """Output of clarification_engine.py."""

    question: str
    kind: Literal["confirm", "disambiguate", "repeat_digit_by_digit", "read_back"] = "confirm"
    candidate_value: Optional[str] = None
    alternative_value: Optional[str] = None
    uncertain_positions: list[int] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    ts_ms: int
    label: str
    detail: Optional[str] = None
    kind: Literal[
        "speech", "capture", "risk", "pause", "clarify", "verify", "resume", "action", "system"
    ] = "system"


class ConversationTurn(BaseModel):
    """One bubble in the conversation view."""

    role: Literal["caller", "agent", "system"]
    text: str
    words: list[Word] = Field(default_factory=list)
    ts_ms: int = 0
    note: Optional[str] = None


class ResolvedEntry(BaseModel):
    """One completed entity resolution this session — feeds the session-history panel."""

    entity_type: str
    value: str
    status: EntityStatus
    required_clarification: bool
    risk_score: Optional[float] = None
    ts_ms: int


class SessionState(BaseModel):
    """Full state broadcast to the frontend over the session WebSocket."""

    session_id: str
    ripcord_enabled: bool = True
    mock_mode: bool = True
    connection_status: Literal["idle", "connecting", "live", "reconnecting", "disconnected"] = "idle"
    transcript: str = ""
    live_partial: str = ""
    entity: Optional[CriticalEntity] = None
    risk: Optional[RiskAssessment] = None
    clarification: Optional[ClarificationQuestion] = None
    verified_value: Optional[str] = None
    action_result: Optional[str] = None
    workflow_paused: bool = False
    escalated: bool = False
    attempts: int = 0
    timeline: list[TimelineEvent] = Field(default_factory=list)
    conversation: list[ConversationTurn] = Field(default_factory=list)
    last_decision_latency_ms: Optional[int] = None
    history: list[ResolvedEntry] = Field(default_factory=list)
