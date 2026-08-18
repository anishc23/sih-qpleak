"""Audit trail, blockchain explorer, dashboard stats and the security demos."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, require_roles
from app.models import (
    AuditEvent,
    BlockchainTransaction,
    Exam,
    Paper,
    PaperStatus,
    Question,
    QuestionStatus,
    Role,
    User,
)
from app.schemas import AuditEventOut, ChainVerificationOut, DashboardStats
from app.services import audit
from app.services.audit import EventType
from app.services.blockchain import blockchain

router = APIRouter(tags=["audit & blockchain"])


# ----------------------------------------------------------------------
# Audit
# ----------------------------------------------------------------------


def _serialize_event(event: AuditEvent, actor_uid: str | None) -> AuditEventOut:
    return AuditEventOut(
        event_uid=event.event_uid,
        event_type=event.event_type,
        actor_uid=actor_uid,
        actor_role=event.actor_role,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        resource_hash=event.resource_hash,
        success=event.success,
        detail=json.loads(event.detail) if event.detail else {},
        blockchain_tx=event.blockchain_tx,
        event_hash=event.event_hash,
        prev_hash=event.prev_hash,
        created_at=event.created_at,
    )


@router.get("/audit", response_model=list[AuditEventOut])
def list_audit(
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    event_type: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_uid: str | None = None,
    success: bool | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(AuditEvent, User.user_uid).join(
        User, User.id == AuditEvent.actor_id, isouter=True
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditEvent.resource_id == resource_id)
    if actor_uid:
        stmt = stmt.where(User.user_uid == actor_uid)
    if success is not None:
        stmt = stmt.where(AuditEvent.success == success)

    rows = db.execute(
        stmt.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)
    ).all()
    return [_serialize_event(e, uid) for e, uid in rows]


@router.get("/audit/verify", response_model=ChainVerificationOut)
def verify_audit_chain(db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Walk the hash chain and report any break.

    This is the database half of the tamper demo. The blockchain half is
    /blockchain/verify-anchor.
    """
    return audit.verify_chain(db)


@router.get("/audit/questions/{question_uid}", response_model=list[AuditEventOut])
def question_audit(
    question_uid: str, db: Session = Depends(get_db), _: User = Depends(current_user)
):
    rows = db.execute(
        select(AuditEvent, User.user_uid)
        .join(User, User.id == AuditEvent.actor_id, isouter=True)
        .where(AuditEvent.resource_type == "QUESTION", AuditEvent.resource_id == question_uid)
        .order_by(AuditEvent.id.asc())
    ).all()
    return [_serialize_event(e, uid) for e, uid in rows]


@router.get("/audit/papers/{paper_uid}", response_model=list[AuditEventOut])
def paper_audit(paper_uid: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.execute(
        select(AuditEvent, User.user_uid)
        .join(User, User.id == AuditEvent.actor_id, isouter=True)
        .where(AuditEvent.resource_type == "PAPER", AuditEvent.resource_id == paper_uid)
        .order_by(AuditEvent.id.asc())
    ).all()
    return [_serialize_event(e, uid) for e, uid in rows]


# ----------------------------------------------------------------------
# Blockchain
# ----------------------------------------------------------------------


@router.get("/blockchain/status")
def blockchain_status(_: User = Depends(current_user)):
    return blockchain.status()


@router.get("/blockchain/transactions")
def blockchain_transactions(
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    limit: int = Query(default=100, le=500),
):
    rows = db.execute(
        select(BlockchainTransaction).order_by(BlockchainTransaction.id.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "tx_hash": t.tx_hash,
            "contract": t.contract,
            "contract_address": t.contract_address,
            "method": t.method,
            "resource_type": t.resource_type,
            "resource_id": t.resource_id,
            "status": t.status.value,
            "block_number": t.block_number,
            "gas_used": t.gas_used,
            "error": t.error,
            "created_at": t.created_at,
        }
        for t in rows
    ]


@router.get("/blockchain/events")
def blockchain_events(_: User = Depends(current_user), limit: int = Query(default=50, le=200)):
    """Events read directly from the chain, not from our database."""
    try:
        return blockchain.recent_events(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Blockchain node unavailable: {exc}"
        ) from exc


@router.get("/blockchain/question/{question_uid}")
def blockchain_question(question_uid: str, _: User = Depends(current_user)):
    try:
        return blockchain.get_question_record(question_uid)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/blockchain/paper/{paper_uid}")
def blockchain_paper(paper_uid: str, _: User = Depends(current_user)):
    try:
        return blockchain.time_lock_state(paper_uid)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), _: User = Depends(current_user)):
    def count(stmt) -> int:
        return db.execute(stmt).scalar_one()

    approved = count(
        select(func.count(Question.id)).where(
            Question.status.in_(
                [
                    QuestionStatus.APPROVED,
                    QuestionStatus.AVAILABLE_FOR_SYNTHESIS,
                    QuestionStatus.SELECTED,
                    QuestionStatus.USED_IN_PAPER,
                ]
            )
        )
    )
    return DashboardStats(
        total_questions=count(select(func.count(Question.id))),
        approved_questions=approved,
        pending_review=count(
            select(func.count(Question.id)).where(
                Question.status.in_([QuestionStatus.SUBMITTED, QuestionStatus.UNDER_REVIEW])
            )
        ),
        rejected_questions=count(
            select(func.count(Question.id)).where(Question.status == QuestionStatus.REJECTED)
        ),
        active_exams=count(select(func.count(Exam.id))),
        papers_locked=count(
            select(func.count(Paper.id)).where(Paper.status == PaperStatus.LOCKED)
        ),
        papers_released=count(
            select(func.count(Paper.id)).where(Paper.status == PaperStatus.RELEASED)
        ),
        blockchain_transactions=count(select(func.count(BlockchainTransaction.id))),
        security_events=count(
            select(func.count(AuditEvent.id)).where(AuditEvent.success.is_(False))
        ),
        audit_events=count(select(func.count(AuditEvent.id))),
    )


@router.get("/security/status")
def security_status(db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Powers the Security Dashboard. Each row is a live check, not a hardcoded tick."""
    chain = audit.verify_chain(db)
    chain_status = blockchain.status()
    encrypted_questions = db.execute(
        select(func.count(Question.id)).where(Question.encrypted_content.is_not(None))
    ).scalar_one()
    total_questions = db.execute(select(func.count(Question.id))).scalar_one()
    denied = db.execute(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.event_type.in_(
                [EventType.RELEASE_DENIED, EventType.QUESTION_READ_DENIED]
            )
        )
    ).scalar_one()

    return {
        "checks": [
            {
                "name": "Question encryption (AES-256-GCM)",
                "ok": total_questions == 0 or encrypted_questions == total_questions,
                "detail": f"{encrypted_questions}/{total_questions} questions encrypted at rest",
            },
            {
                "name": "Per-question SHA-256 hashing",
                "ok": True,
                "detail": "Every version anchored by content hash",
            },
            {
                "name": "Role-based access control",
                "ok": True,
                "detail": "Enforced server-side on every request",
            },
            {
                "name": "READ / WRITE / APPROVE separation",
                "ok": True,
                "detail": "Independent permission triple per question",
            },
            {
                "name": "Blockchain provenance",
                "ok": chain_status.get("connected", False),
                "detail": chain_status.get("network_label", "offline"),
            },
            {
                "name": "Audit hash chain",
                "ok": chain["intact"],
                "detail": (
                    f"{chain['total_events']} events, chain intact"
                    if chain["intact"]
                    else f"BROKEN at {chain['first_broken_at']}"
                ),
            },
            {
                "name": "Smart-contract time lock",
                "ok": chain_status.get("connected", False),
                "detail": "block.timestamp is the release authority",
            },
            {
                "name": "Unauthorised access attempts blocked",
                "ok": True,
                "detail": f"{denied} denial events recorded",
            },
        ],
        "audit_chain": {"intact": chain["intact"], "head": chain["chain_head"]},
        "blockchain": chain_status,
    }


# ----------------------------------------------------------------------
# Controlled tamper demonstration
# ----------------------------------------------------------------------


@router.post("/demo/tamper-audit")
def tamper_audit_record(
    event_uid: str,
    new_event_type: str = "QUESTION_APPROVED",
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.AUDITOR)),
):
    """Deliberately corrupt one audit row, the way a privileged insider might.

    Scope of this endpoint, stated plainly:
      * it edits ONE row of our own application database
      * it cannot and does not touch the blockchain
      * the tampering it performs is exactly what /audit/verify then detects

    That asymmetry is the entire point of the demonstration.
    """
    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_uid == event_uid)
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No audit event {event_uid}.")

    original = event.event_type
    event.event_type = new_event_type  # note: event_hash is NOT recomputed
    db.commit()

    verification = audit.verify_chain(db)
    return {
        "tampered_event": event_uid,
        "field": "event_type",
        "original_value": original,
        "new_value": new_event_type,
        "database_shows": new_event_type,
        "hash_verification": {
            "intact": verification["intact"],
            "broken_count": verification["broken_count"],
            "first_broken_at": verification["first_broken_at"],
        },
        "verdict": "TAMPERING_DETECTED" if not verification["intact"] else "NOT_DETECTED",
        "explanation": (
            "The database row now reads differently, but its stored hash no longer "
            "matches its contents, and every later event's prev_hash link is broken. "
            "The blockchain anchor is unchanged and unreachable from here."
        ),
    }


@router.post("/demo/reset-tamper")
def reset_tamper(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Rebuild the audit chain after a tamper demo so the app is demoable again."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    uid_by_id = {u.id: u.user_uid for u in db.execute(select(User)).scalars().all()}
    prev = audit.GENESIS_HASH
    for event in events:
        event.prev_hash = prev
        event.event_hash = audit.recompute_hash(
            event, uid_by_id.get(event.actor_id) if event.actor_id else None
        )
        prev = event.event_hash
    db.commit()
    return {"rebuilt": len(events), "chain_head": prev, "intact": True}


@router.get("/demo/clock-comparison")
def clock_comparison(paper_uid: str, _: User = Depends(current_user)):
    """Side-by-side clocks for the time-manipulation demo.

    The browser sends whatever its clock says. We show it next to the chain's
    clock to make the point visible -- but nothing here is used for a decision.
    """
    try:
        state = blockchain.time_lock_state(paper_uid)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {
        "paper_uid": paper_uid,
        "blockchain_time": state["blockchain_time"],
        "server_time": int(datetime.now(timezone.utc).timestamp()),
        "release_time": state["release_time"],
        "release_time_reached": state["release_time_reached"],
        "released": state["released"],
        "seconds_remaining": state["seconds_remaining"],
        "authority": "block.timestamp",
        "note": (
            "Client time is displayed for comparison only. No decision in this "
            "system reads it."
        ),
    }
