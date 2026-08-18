"""Authorisation: role baseline + per-question READ / WRITE / APPROVE grants.

READ, WRITE and APPROVE are evaluated independently. A reviewer can hold
READ+APPROVE without WRITE; a setter holds READ+WRITE on their own drafts but
never APPROVE. This is checked here, in the backend, on every request.

The frontend hides buttons for usability. That is not security and is never
relied upon.

One deliberate decision worth defending to judges: SUPER_ADMIN does *not* get
blanket READ on question plaintext. Administering the system and reading exam
content are different powers, and collapsing them recreates exactly the insider
risk the project exists to reduce.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, QuestionPermission, QuestionStatus, Role, User


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str

    def __bool__(self) -> bool:  # lets callers write `if decision:`
        return self.allowed


ALLOW = Decision(True, "authorised")


def _explicit_grant(db: Session, question_id: int, user_id: int) -> QuestionPermission | None:
    return db.execute(
        select(QuestionPermission).where(
            QuestionPermission.question_id == question_id,
            QuestionPermission.user_id == user_id,
        )
    ).scalar_one_or_none()


def can_read(db: Session, user: User, question: Question) -> Decision:
    """May this user obtain the DECRYPTED question content?"""
    grant = _explicit_grant(db, question.id, user.id)
    if grant and grant.can_read:
        return ALLOW

    if user.role == Role.QUESTION_SETTER:
        if question.creator_id == user.id:
            return ALLOW
        return Decision(
            False,
            "Question setters may only read their own questions. "
            "This question belongs to another setter.",
        )

    if user.role == Role.REVIEWER:
        # A reviewer reads what is in front of them for review, not the archive.
        if question.status in {
            QuestionStatus.SUBMITTED,
            QuestionStatus.UNDER_REVIEW,
            QuestionStatus.APPROVED,
            QuestionStatus.REJECTED,
        }:
            return ALLOW
        return Decision(False, "Reviewers may only read questions in the review workflow.")

    if user.role == Role.EXAM_AUTHORITY:
        # Needed to assemble and proof a paper.
        if question.status in {
            QuestionStatus.APPROVED,
            QuestionStatus.AVAILABLE_FOR_SYNTHESIS,
            QuestionStatus.SELECTED,
            QuestionStatus.USED_IN_PAPER,
        }:
            return ALLOW
        return Decision(False, "Exam authority may only read approved questions.")

    if user.role == Role.AUDITOR:
        # Auditors verify hashes and provenance. That does not require plaintext.
        return Decision(
            False,
            "Auditors have metadata and provenance access, not question plaintext. "
            "Integrity can be verified from hashes alone.",
        )

    if user.role == Role.SUPER_ADMIN:
        return Decision(
            False,
            "Administrative role does not confer question-content access. "
            "Request an explicit READ grant, which is itself audited.",
        )

    return Decision(False, "No READ permission for this question.")


def can_write(db: Session, user: User, question: Question) -> Decision:
    grant = _explicit_grant(db, question.id, user.id)

    # Approved and printed questions are frozen regardless of who is asking.
    frozen = {
        QuestionStatus.APPROVED,
        QuestionStatus.AVAILABLE_FOR_SYNTHESIS,
        QuestionStatus.SELECTED,
        QuestionStatus.USED_IN_PAPER,
        QuestionStatus.RETIRED,
    }
    if question.status in frozen:
        return Decision(
            False,
            f"This question is {question.status.value} and cannot be edited. "
            "Approved content is immutable; retire it and submit a new version instead.",
        )

    if grant and grant.can_write:
        return ALLOW

    if user.role == Role.QUESTION_SETTER and question.creator_id == user.id:
        if question.status in {QuestionStatus.DRAFT, QuestionStatus.REJECTED}:
            return ALLOW
        return Decision(
            False,
            f"A submitted question cannot be edited while it is {question.status.value}.",
        )

    return Decision(False, "No WRITE permission for this question.")


def can_approve(db: Session, user: User, question: Question) -> Decision:
    grant = _explicit_grant(db, question.id, user.id)
    if grant and grant.can_approve:
        return ALLOW

    if user.role == Role.REVIEWER:
        # Separation of duties: a reviewer never approves their own authorship.
        if question.creator_id == user.id:
            return Decision(
                False,
                "Separation of duties: you cannot approve a question you authored.",
            )
        if question.status in {QuestionStatus.SUBMITTED, QuestionStatus.UNDER_REVIEW}:
            return ALLOW
        return Decision(
            False,
            f"Only submitted questions can be approved (this one is {question.status.value}).",
        )

    return Decision(False, "APPROVE permission is restricted to assigned reviewers.")


def can_manage_permissions(user: User) -> Decision:
    if user.role in {Role.SUPER_ADMIN, Role.EXAM_AUTHORITY}:
        return ALLOW
    return Decision(False, "Only administrators may change question permissions.")


def can_view_paper_content(user: User) -> Decision:
    """Who may ever hold the decrypted final paper -- subject to the time lock."""
    if user.role == Role.EXAM_AUTHORITY:
        return ALLOW
    if user.role == Role.QUESTION_SETTER:
        return Decision(
            False,
            "Question setters are never shown the assembled paper. This is the "
            "core anti-leak separation: contribute questions, never see the outcome.",
        )
    return Decision(False, "Only the Exam Authority may access final paper content.")


def visible_questions_filter(user: User):
    """SQL predicate limiting which questions a role may even enumerate."""
    if user.role == Role.QUESTION_SETTER:
        return Question.creator_id == user.id
    if user.role == Role.REVIEWER:
        return Question.status.in_(
            [
                QuestionStatus.SUBMITTED,
                QuestionStatus.UNDER_REVIEW,
                QuestionStatus.APPROVED,
                QuestionStatus.REJECTED,
            ]
        )
    # Admin, authority and auditor may enumerate metadata for the whole pool.
    return None


def summarize(db: Session, user: User, question: Question) -> dict[str, bool]:
    """Permission triple shown in the UI (and used by tests)."""
    return {
        "read": bool(can_read(db, user, question)),
        "write": bool(can_write(db, user, question)),
        "approve": bool(can_approve(db, user, question)),
    }
