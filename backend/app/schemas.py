"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Difficulty, PaperStatus, QuestionStatus, QuestionType, Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role
    department: str | None = None


class UserOut(ORMModel):
    user_uid: str
    name: str
    email: str
    role: Role
    department: str | None = None
    is_active: bool
    created_at: datetime


# ----------------------------------------------------------------------
# Questions
# ----------------------------------------------------------------------


class QuestionCreate(BaseModel):
    content: str = Field(min_length=10, max_length=8000)
    subject: str = Field(min_length=2, max_length=120)
    topic: str = Field(min_length=2, max_length=120)
    difficulty: Difficulty
    question_type: QuestionType = QuestionType.SHORT_ANSWER
    marks: int = Field(default=5, ge=1, le=100)
    learning_objective: str | None = Field(default=None, max_length=255)


class QuestionUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=10, max_length=8000)
    subject: str | None = None
    topic: str | None = None
    difficulty: Difficulty | None = None
    question_type: QuestionType | None = None
    marks: int | None = Field(default=None, ge=1, le=100)
    learning_objective: str | None = None
    change_note: str | None = Field(default=None, max_length=500)


class PermissionsOut(BaseModel):
    read: bool
    write: bool
    approve: bool


class QuestionOut(BaseModel):
    """Metadata only. Content is never included -- see /questions/{uid}/read."""

    question_uid: str
    subject: str
    topic: str
    difficulty: Difficulty
    question_type: QuestionType
    marks: int
    learning_objective: str | None
    content_hash: str
    version: int
    status: QuestionStatus
    creator_uid: str
    creator_name: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    permissions: PermissionsOut


class QuestionContentOut(BaseModel):
    question_uid: str
    content: str
    content_hash: str
    version: int
    access_recorded: bool
    blockchain: dict[str, Any] | None = None


class ChainReceipt(BaseModel):
    submitted: bool
    confirmed: bool = False
    tx_hash: str | None = None
    block_number: int | None = None
    status: str | None = None
    error: str | None = None
    message: str | None = None


class QuestionCreatedOut(BaseModel):
    question: QuestionOut
    encryption: dict[str, Any]
    blockchain: ChainReceipt


class ReviewRequest(BaseModel):
    approve: bool
    comment: str | None = Field(default=None, max_length=2000)


class PermissionGrant(BaseModel):
    user_uid: str
    can_read: bool = False
    can_write: bool = False
    can_approve: bool = False


class VersionOut(ORMModel):
    version: int
    content_hash: str
    change_note: str | None
    created_at: datetime


# ----------------------------------------------------------------------
# Exams and papers
# ----------------------------------------------------------------------


class BlueprintIn(BaseModel):
    difficulty_distribution: dict[str, float] = Field(
        default_factory=lambda: {"EASY": 30, "MEDIUM": 50, "HARD": 20}
    )
    topic_distribution: dict[str, float]
    type_distribution: dict[str, float] | None = None


class ExamCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    subject: str
    total_marks: int = Field(default=100, ge=10, le=1000)
    question_count: int = Field(default=20, ge=1, le=200)
    scheduled_at: datetime | None = None
    blueprint: BlueprintIn


class ExamOut(BaseModel):
    exam_uid: str
    title: str
    subject: str
    total_marks: int
    question_count: int
    scheduled_at: datetime | None
    blueprint: dict[str, Any] | None
    paper_count: int
    created_at: datetime


class GeneratePaperRequest(BaseModel):
    apply_variations: bool = True


class PaperQuestionOut(BaseModel):
    sequence: int
    question_uid: str
    topic: str
    difficulty: Difficulty
    marks: int
    selection_score: float
    selection_reason: str | None
    used_variation: bool


class PaperOut(BaseModel):
    paper_uid: str
    exam_uid: str
    exam_title: str
    status: PaperStatus
    paper_hash: str | None
    release_time: datetime | None
    released_at: datetime | None
    contract_address: str | None
    registration_tx: str | None
    release_tx: str | None
    question_count: int
    blueprint_compliance: dict[str, Any] | None
    synthesis_report: dict[str, Any] | None
    created_at: datetime


class PaperDetailOut(PaperOut):
    questions: list[PaperQuestionOut]


class RegisterPaperRequest(BaseModel):
    release_in_seconds: int | None = Field(
        default=None, ge=5, le=60 * 60 * 24 * 365,
        description="Demo convenience: release this many seconds from now.",
    )
    release_time: datetime | None = None


class PaperContentOut(BaseModel):
    paper_uid: str
    content: str
    paper_hash: str
    released_at: datetime | None
    blockchain_verified: bool


# ----------------------------------------------------------------------
# Audit / blockchain
# ----------------------------------------------------------------------


class AuditEventOut(BaseModel):
    event_uid: str
    event_type: str
    actor_uid: str | None
    actor_role: str | None
    resource_type: str
    resource_id: str
    resource_hash: str | None
    success: bool
    detail: dict[str, Any] | None
    blockchain_tx: str | None
    event_hash: str
    prev_hash: str
    created_at: datetime


class ChainVerificationOut(BaseModel):
    total_events: int
    intact: bool
    broken_count: int
    first_broken_at: str | None
    broken_events: list[dict[str, Any]]
    chain_head: str


class DashboardStats(BaseModel):
    total_questions: int
    approved_questions: int
    pending_review: int
    rejected_questions: int
    active_exams: int
    papers_locked: int
    papers_released: int
    blockchain_transactions: int
    security_events: int
    audit_events: int


TokenResponse.model_rebuild()
