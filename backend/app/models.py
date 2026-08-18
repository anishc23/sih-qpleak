"""SQLAlchemy models.

Design rules enforced here:
  * Question plaintext is never stored. `encrypted_content` holds AES-256-GCM
    ciphertext; there is deliberately no `content` column to write to by mistake.
  * Every mutation produces an `AuditEvent`, and audit events are chained by
    hash so a silent UPDATE breaks verification.
  * Encryption keys are stored wrapped, never bare.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------------
# Enumerations
# ----------------------------------------------------------------------


class Role(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    QUESTION_SETTER = "QUESTION_SETTER"
    REVIEWER = "REVIEWER"
    EXAM_AUTHORITY = "EXAM_AUTHORITY"
    AUDITOR = "AUDITOR"


class QuestionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AVAILABLE_FOR_SYNTHESIS = "AVAILABLE_FOR_SYNTHESIS"
    SELECTED = "SELECTED"
    USED_IN_PAPER = "USED_IN_PAPER"
    RETIRED = "RETIRED"


class Difficulty(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class QuestionType(str, enum.Enum):
    SHORT_ANSWER = "SHORT_ANSWER"
    LONG_ANSWER = "LONG_ANSWER"
    MCQ = "MCQ"
    NUMERICAL = "NUMERICAL"
    PROBLEM = "PROBLEM"


class PaperStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    ENCRYPTED = "ENCRYPTED"
    BLOCKCHAIN_REGISTERED = "BLOCKCHAIN_REGISTERED"
    LOCKED = "LOCKED"
    RELEASED = "RELEASED"


class AccessType(str, enum.Enum):
    READ = "READ"
    WRITE = "WRITE"
    APPROVE = "APPROVE"
    SELECT = "SELECT"
    EXPORT = "EXPORT"


class ChainTxStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"  # node was down; nothing was faked


# ----------------------------------------------------------------------
# Identity
# ----------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="creator", foreign_keys="Question.creator_id"
    )

    @property
    def actor_fingerprint(self) -> str:
        """Pseudonymous identifier used on chain. Never the email."""
        return self.user_uid


# ----------------------------------------------------------------------
# Questions
# ----------------------------------------------------------------------


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    subject: Mapped[str] = mapped_column(String(120), index=True)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty), index=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType))
    marks: Mapped[int] = mapped_column(Integer, default=5)
    learning_objective: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AES-256-GCM: nonce || ciphertext || tag. No plaintext column exists.
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)
    # SHA-256 of the canonical plaintext, hex encoded.
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # The per-question data key, itself encrypted under the master key.
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)

    # A short, non-sensitive fingerprint used only for duplicate detection so the
    # similarity engine never needs to decrypt the whole pool.
    search_terms: Mapped[str] = mapped_column(Text, default="")

    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus), default=QuestionStatus.DRAFT, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Set when this question is a synthesis-generated variation of another.
    derived_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id"), nullable=True
    )

    creator: Mapped[User] = relationship(back_populates="questions", foreign_keys=[creator_id])
    versions: Mapped[list["QuestionVersion"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionVersion.version"
    )
    permissions: Mapped[list["QuestionPermission"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["QuestionReview"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionVersion(Base):
    """Append-only history. Editing a question never overwrites a prior row."""

    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version", name="uq_question_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)
    content_hash: Mapped[str] = mapped_column(String(64))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="versions")


class QuestionPermission(Base):
    """READ / WRITE / APPROVE are independent grants, not a single 'access' flag.

    Role gives a baseline; this table grants beyond it. Both are checked in the
    backend -- the frontend hiding a button is not access control.
    """

    __tablename__ = "question_permissions"
    __table_args__ = (
        UniqueConstraint("question_id", "user_id", name="uq_question_permission"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="permissions")


class QuestionAccessLog(Base):
    __tablename__ = "question_access_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    access_type: Mapped[AccessType] = mapped_column(Enum(AccessType))
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QuestionReview(Base):
    __tablename__ = "question_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(32))  # APPROVED / REJECTED / REVISION_REQUESTED
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="reviews")


# ----------------------------------------------------------------------
# Exams and papers
# ----------------------------------------------------------------------


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(120))
    total_marks: Mapped[int] = mapped_column(Integer, default=100)
    question_count: Mapped[int] = mapped_column(Integer, default=20)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    blueprint: Mapped["ExamBlueprint | None"] = relationship(
        back_populates="exam", uselist=False, cascade="all, delete-orphan"
    )
    papers: Mapped[list["Paper"]] = relationship(back_populates="exam")


class ExamBlueprint(Base):
    """Difficulty / topic / type distribution the synthesis engine must satisfy."""

    __tablename__ = "exam_blueprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), unique=True)
    # JSON-encoded percentage maps, e.g. {"EASY": 30, "MEDIUM": 50, "HARD": 20}
    difficulty_distribution: Mapped[str] = mapped_column(Text)
    topic_distribution: Mapped[str] = mapped_column(Text)
    type_distribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    exam: Mapped[Exam] = relationship(back_populates="blueprint")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus), default=PaperStatus.DRAFT, index=True
    )

    # Populated only once the paper is finalised. Until encryption, the assembled
    # paper exists only as the ordered PaperQuestion rows.
    encrypted_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    wrapped_key: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    paper_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    release_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contract_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registration_tx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    release_tx: Mapped[str | None] = mapped_column(String(80), nullable=True)

    blueprint_compliance: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    synthesis_report: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    exam: Mapped[Exam] = relationship(back_populates="papers")
    questions: Mapped[list["PaperQuestion"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperQuestion.sequence"
    )


class PaperQuestion(Base):
    __tablename__ = "paper_questions"
    __table_args__ = (UniqueConstraint("paper_id", "sequence", name="uq_paper_sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    marks: Mapped[int] = mapped_column(Integer)
    selection_score: Mapped[float] = mapped_column(Float, default=0.0)
    selection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    used_variation: Mapped[bool] = mapped_column(Boolean, default=False)

    paper: Mapped[Paper] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship()


class QuestionVariation(Base):
    """An engine-generated rewording awaiting reviewer approval.

    Provenance for every variation is retained so a reviewer can always see what
    changed and why -- the engine is never trusted blindly.
    """

    __tablename__ = "question_variations"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    original_hash: Mapped[str] = mapped_column(String(64))
    generated_hash: Mapped[str] = mapped_column(String(64))
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)
    similarity_score: Mapped[float] = mapped_column(Float)
    generation_method: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ----------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------


class AuditEvent(Base):
    """Hash-chained application audit log.

    `event_hash = SHA256(prev_hash || canonical_payload)`. Editing any historical
    row breaks every subsequent link, which is what the tamper demo detects --
    and the chain head is additionally anchored on the blockchain.
    """

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_resource", "resource_type", "resource_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64))
    resource_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    prev_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), index=True)

    blockchain_tx: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BlockchainTransaction(Base):
    __tablename__ = "blockchain_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    contract: Mapped[str] = mapped_column(String(64))
    contract_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ChainTxStatus] = mapped_column(
        Enum(ChainTxStatus), default=ChainTxStatus.PENDING, index=True
    )
    block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gas_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
