"""Question lifecycle orchestration: encrypt -> hash -> persist -> anchor -> audit.

Every path through this module keeps four things in step: the ciphertext, the
content hash, the on-chain anchor, and the audit event. If the chain is
unreachable the first three still happen and the anchor is recorded as
UNAVAILABLE -- never faked.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Difficulty,
    Question,
    QuestionAccessLog,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
    Role,
    User,
    AccessType,
)
from app.security.crypto import DecryptionError, content_hash, decrypt, encrypt
from app.security.keyvault import create_wrapped_key, decrypt_key
from app.services import audit, permissions
from app.services.audit import EventType
from app.services.blockchain import blockchain
from app.services.synthesis import tokenize

# Mirrors the Lifecycle enum in QuestionRegistry.sol
CHAIN_LIFECYCLE = {
    QuestionStatus.DRAFT: 1,
    QuestionStatus.SUBMITTED: 2,
    QuestionStatus.UNDER_REVIEW: 3,
    QuestionStatus.APPROVED: 4,
    QuestionStatus.REJECTED: 5,
    QuestionStatus.SELECTED: 6,
    QuestionStatus.USED_IN_PAPER: 7,
    QuestionStatus.RETIRED: 8,
}


class QuestionError(Exception):
    """Business-rule violation, surfaced to the client as 400/403."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def next_question_uid(db: Session) -> str:
    count = db.execute(select(func.count(Question.id))).scalar_one()
    return f"Q-{count + 1:06d}"


def _search_terms(text: str) -> str:
    """Non-reversible token bag used for duplicate detection.

    Stores only stemmed, stopword-filtered tokens in sorted order -- enough for
    TF-IDF, not enough to reconstruct the question.
    """
    return " ".join(sorted(set(tokenize(text))))


# ----------------------------------------------------------------------
# Create / update
# ----------------------------------------------------------------------


def create_question(
    db: Session,
    *,
    creator: User,
    content: str,
    subject: str,
    topic: str,
    difficulty: Difficulty,
    question_type: QuestionType,
    marks: int,
    learning_objective: str | None = None,
    ip_address: str | None = None,
) -> tuple[Question, dict]:
    if creator.role not in {Role.QUESTION_SETTER, Role.SUPER_ADMIN}:
        raise QuestionError("Only question setters may create questions.", 403)
    if not content.strip():
        raise QuestionError("Question content cannot be empty.")

    dek, wrapped = create_wrapped_key("question")
    digest = content_hash(content)

    question = Question(
        question_uid=next_question_uid(db),
        creator_id=creator.id,
        subject=subject.strip(),
        topic=topic.strip(),
        difficulty=difficulty,
        question_type=question_type,
        marks=marks,
        learning_objective=learning_objective,
        encrypted_content=encrypt(content, dek),
        content_hash=digest,
        wrapped_key=wrapped,
        search_terms=_search_terms(content),
        version=1,
        status=QuestionStatus.DRAFT,
    )
    db.add(question)
    db.flush()

    db.add(
        QuestionVersion(
            question_id=question.id,
            version=1,
            encrypted_content=question.encrypted_content,
            wrapped_key=wrapped,
            content_hash=digest,
            changed_by=creator.id,
            change_note="Initial creation",
        )
    )

    audit.record(
        db,
        event_type=EventType.QUESTION_CREATED,
        actor=creator,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=digest,
        detail={"subject": subject, "topic": topic, "difficulty": difficulty.value},
        ip_address=ip_address,
    )
    audit.record(
        db,
        event_type=EventType.QUESTION_ENCRYPTED,
        actor=creator,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=digest,
        detail={"algorithm": "AES-256-GCM", "hash_algorithm": "SHA-256"},
        ip_address=ip_address,
    )

    chain = blockchain.register_question(
        db,
        question_uid=question.question_uid,
        content_hash=digest,
        creator_uid=creator.user_uid,
    )
    return question, _chain_payload(chain)


def update_question(
    db: Session,
    *,
    editor: User,
    question: Question,
    content: str | None = None,
    change_note: str | None = None,
    ip_address: str | None = None,
    **metadata,
) -> tuple[Question, dict]:
    decision = permissions.can_write(db, editor, question)
    if not decision:
        _log_access(db, question, editor, AccessType.WRITE, False, decision.reason, ip_address)
        raise QuestionError(decision.reason, 403)

    chain_payload: dict = {"submitted": False}

    for field_name in ("subject", "topic", "marks", "learning_objective"):
        if field_name in metadata and metadata[field_name] is not None:
            setattr(question, field_name, metadata[field_name])
    if metadata.get("difficulty") is not None:
        question.difficulty = metadata["difficulty"]
    if metadata.get("question_type") is not None:
        question.question_type = metadata["question_type"]

    if content is not None and content.strip():
        digest = content_hash(content)
        if digest != question.content_hash:
            # New content means a new version. The old row stays untouched.
            dek, wrapped = create_wrapped_key("question")
            question.version += 1
            question.encrypted_content = encrypt(content, dek)
            question.wrapped_key = wrapped
            question.content_hash = digest
            question.search_terms = _search_terms(content)

            db.add(
                QuestionVersion(
                    question_id=question.id,
                    version=question.version,
                    encrypted_content=question.encrypted_content,
                    wrapped_key=wrapped,
                    content_hash=digest,
                    changed_by=editor.id,
                    change_note=change_note or "Content revised",
                )
            )
            chain = blockchain.update_question(
                db,
                question_uid=question.question_uid,
                content_hash=digest,
                actor_uid=editor.user_uid,
            )
            chain_payload = _chain_payload(chain)

    question.updated_at = datetime.now(timezone.utc)
    _log_access(db, question, editor, AccessType.WRITE, True, None, ip_address)
    audit.record(
        db,
        event_type=EventType.QUESTION_UPDATED,
        actor=editor,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=question.content_hash,
        detail={"version": question.version, "note": change_note},
        ip_address=ip_address,
    )
    return question, chain_payload


# ----------------------------------------------------------------------
# Read (the security-sensitive operation)
# ----------------------------------------------------------------------


def read_question_content(
    db: Session, *, reader: User, question: Question, ip_address: str | None = None
) -> str:
    """Decrypt a question. Every call is authorised, logged and anchored.

    Reading is treated as a security event in its own right -- that is the whole
    point of separating READ from WRITE.
    """
    decision = permissions.can_read(db, reader, question)
    if not decision:
        _log_access(db, question, reader, AccessType.READ, False, decision.reason, ip_address)
        audit.record(
            db,
            event_type=EventType.QUESTION_READ_DENIED,
            actor=reader,
            resource_type="QUESTION",
            resource_id=question.question_uid,
            resource_hash=question.content_hash,
            success=False,
            detail={"reason": decision.reason},
            ip_address=ip_address,
        )
        db.commit()
        raise QuestionError(decision.reason, 403)

    try:
        dek = decrypt_key(question.wrapped_key, "question")
        plaintext = decrypt(question.encrypted_content, dek)
    except DecryptionError as exc:
        audit.record(
            db,
            event_type=EventType.TAMPERING_DETECTED,
            actor=reader,
            resource_type="QUESTION",
            resource_id=question.question_uid,
            success=False,
            detail={"error": str(exc)},
            ip_address=ip_address,
        )
        db.commit()
        raise QuestionError(
            "Integrity failure: the stored ciphertext failed authentication. "
            "This question may have been tampered with.",
            409,
        ) from exc

    _log_access(db, question, reader, AccessType.READ, True, None, ip_address)
    audit.record(
        db,
        event_type=EventType.QUESTION_READ,
        actor=reader,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=question.content_hash,
        ip_address=ip_address,
    )
    blockchain.record_access(
        db,
        question_uid=question.question_uid,
        actor_uid=reader.user_uid,
        access_type="READ",
    )
    return plaintext


def decrypt_for_system(question: Question) -> str:
    """Internal decryption for the synthesis engine.

    Not user-facing: no human sees this text. It is used to build TF-IDF vectors
    and to assemble the paper, both of which happen inside the trust boundary.
    """
    dek = decrypt_key(question.wrapped_key, "question")
    return decrypt(question.encrypted_content, dek)


# ----------------------------------------------------------------------
# Workflow transitions
# ----------------------------------------------------------------------


def submit_question(
    db: Session, *, actor: User, question: Question, ip_address: str | None = None
) -> dict:
    if question.creator_id != actor.id and actor.role != Role.SUPER_ADMIN:
        raise QuestionError("Only the author may submit this question.", 403)
    if question.status not in {QuestionStatus.DRAFT, QuestionStatus.REJECTED}:
        raise QuestionError(f"A {question.status.value} question cannot be submitted.")

    _transition(db, question, QuestionStatus.SUBMITTED, actor)
    audit.record(
        db,
        event_type=EventType.QUESTION_SUBMITTED,
        actor=actor,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=question.content_hash,
        ip_address=ip_address,
    )
    chain = blockchain.set_lifecycle(
        db,
        question_uid=question.question_uid,
        lifecycle=CHAIN_LIFECYCLE[QuestionStatus.SUBMITTED],
        actor_uid=actor.user_uid,
    )
    return _chain_payload(chain)


def review_question(
    db: Session,
    *,
    reviewer: User,
    question: Question,
    approve: bool,
    comment: str | None = None,
    ip_address: str | None = None,
) -> dict:
    decision = permissions.can_approve(db, reviewer, question)
    if not decision:
        _log_access(db, question, reviewer, AccessType.APPROVE, False, decision.reason, ip_address)
        raise QuestionError(decision.reason, 403)

    from app.models import QuestionReview

    # The chain requires SUBMITTED -> UNDER_REVIEW before a verdict.
    if question.status == QuestionStatus.SUBMITTED:
        _transition(db, question, QuestionStatus.UNDER_REVIEW, reviewer)
        blockchain.set_lifecycle(
            db,
            question_uid=question.question_uid,
            lifecycle=CHAIN_LIFECYCLE[QuestionStatus.UNDER_REVIEW],
            actor_uid=reviewer.user_uid,
        )

    target = QuestionStatus.APPROVED if approve else QuestionStatus.REJECTED
    _transition(db, question, target, reviewer)

    if approve:
        question.approved_at = datetime.now(timezone.utc)
        question.approved_by = reviewer.id

    db.add(
        QuestionReview(
            question_id=question.id,
            reviewer_id=reviewer.id,
            decision="APPROVED" if approve else "REJECTED",
            comment=comment,
            reviewed_version=question.version,
        )
    )
    _log_access(db, question, reviewer, AccessType.APPROVE, True, None, ip_address)
    audit.record(
        db,
        event_type=EventType.QUESTION_APPROVED if approve else EventType.QUESTION_REJECTED,
        actor=reviewer,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=question.content_hash,
        detail={"comment": comment, "version": question.version},
        ip_address=ip_address,
    )
    chain = blockchain.set_lifecycle(
        db,
        question_uid=question.question_uid,
        lifecycle=CHAIN_LIFECYCLE[target],
        actor_uid=reviewer.user_uid,
    )

    if approve:
        # Approved questions enter the synthesis pool. This is an application
        # state only; on chain APPROVED is the terminal review state.
        question.status = QuestionStatus.AVAILABLE_FOR_SYNTHESIS
    return _chain_payload(chain)


def _transition(db: Session, question: Question, target: QuestionStatus, actor: User) -> None:
    question.status = target
    question.updated_at = datetime.now(timezone.utc)
    db.flush()


def _log_access(
    db: Session,
    question: Question,
    user: User,
    access_type: AccessType,
    granted: bool,
    reason: str | None,
    ip_address: str | None,
) -> None:
    db.add(
        QuestionAccessLog(
            question_id=question.id,
            user_id=user.id,
            access_type=access_type,
            granted=granted,
            reason=reason,
            ip_address=ip_address,
        )
    )


def _chain_payload(result) -> dict:
    """Uniform blockchain outcome for API responses. Never fabricates a hash."""
    return {
        "submitted": True,
        "confirmed": result.ok,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "status": result.status.value,
        "error": result.error,
        "message": (
            "Anchored on chain."
            if result.ok
            else "Blockchain node unavailable - the anchor is queued, not faked."
        ),
    }


def verify_integrity(db: Session, question: Question) -> dict:
    """Compare stored ciphertext, recomputed hash and the on-chain anchor."""
    result: dict = {
        "question_uid": question.question_uid,
        "stored_hash": question.content_hash,
        "ciphertext_authentic": None,
        "recomputed_hash": None,
        "database_consistent": None,
        "blockchain_match": None,
        "blockchain_available": True,
        "verdict": "UNKNOWN",
    }
    try:
        plaintext = decrypt_for_system(question)
        result["ciphertext_authentic"] = True
        recomputed = content_hash(plaintext)
        result["recomputed_hash"] = recomputed
        result["database_consistent"] = recomputed == question.content_hash
    except DecryptionError as exc:
        result["ciphertext_authentic"] = False
        result["database_consistent"] = False
        result["error"] = str(exc)

    try:
        result["blockchain_match"] = blockchain.verify_question_hash(
            question.question_uid, question.content_hash
        )
    except Exception as exc:
        result["blockchain_available"] = False
        result["blockchain_error"] = str(exc)

    if result["database_consistent"] and result["blockchain_match"]:
        result["verdict"] = "VERIFIED"
    elif result["blockchain_match"] is False and result["blockchain_available"]:
        result["verdict"] = "TAMPERING_DETECTED"
    elif result["database_consistent"] is False:
        result["verdict"] = "TAMPERING_DETECTED"
    else:
        result["verdict"] = "UNVERIFIED_CHAIN_OFFLINE"
    return result
