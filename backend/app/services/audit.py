"""Hash-chained audit log.

Each event stores the hash of its predecessor:

    event_hash = SHA256(prev_hash || canonical_json(payload))

That makes the log tamper-*evident* on its own: editing row N invalidates row
N+1's link, and so on to the head. The chain head is then anchored on the
blockchain, which is what makes it tamper-evident against someone who can
rewrite the whole table -- they cannot rewrite the anchor.

This is the mechanism behind the "DATABASE vs BLOCKCHAIN" demo: we let an
operator edit an audit row through a clearly-marked demo endpoint, then run
verification and show exactly which link broke.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, User
from app.security.crypto import sha256_hex

GENESIS_HASH = "0" * 64


class EventType:
    """Canonical audit event names. Strings live here, not scattered in routes."""

    USER_LOGIN = "USER_LOGIN"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    USER_CREATED = "USER_CREATED"

    QUESTION_CREATED = "QUESTION_CREATED"
    QUESTION_ENCRYPTED = "QUESTION_ENCRYPTED"
    QUESTION_UPDATED = "QUESTION_UPDATED"
    QUESTION_SUBMITTED = "QUESTION_SUBMITTED"
    QUESTION_READ = "QUESTION_READ"
    QUESTION_READ_DENIED = "QUESTION_READ_DENIED"
    QUESTION_APPROVED = "QUESTION_APPROVED"
    QUESTION_REJECTED = "QUESTION_REJECTED"
    QUESTION_SELECTED = "QUESTION_SELECTED"
    QUESTION_RETIRED = "QUESTION_RETIRED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"

    VARIATION_GENERATED = "VARIATION_GENERATED"
    VARIATION_APPROVED = "VARIATION_APPROVED"

    PAPER_GENERATED = "PAPER_GENERATED"
    PAPER_APPROVED = "PAPER_APPROVED"
    PAPER_ENCRYPTED = "PAPER_ENCRYPTED"
    PAPER_REGISTERED = "PAPER_REGISTERED"
    PAPER_TIME_LOCKED = "PAPER_TIME_LOCKED"
    RELEASE_ATTEMPTED = "RELEASE_ATTEMPTED"
    RELEASE_DENIED = "RELEASE_DENIED"
    PAPER_RELEASED = "PAPER_RELEASED"
    PAPER_DECRYPTED = "PAPER_DECRYPTED"

    INTEGRITY_VERIFIED = "INTEGRITY_VERIFIED"
    TAMPERING_DETECTED = "TAMPERING_DETECTED"
    DEMO_AUDIT_TAMPERED = "DEMO_AUDIT_TAMPERED"


def _canonical_payload(
    *,
    event_uid: str,
    event_type: str,
    actor_uid: str | None,
    actor_role: str | None,
    resource_type: str,
    resource_id: str,
    resource_hash: str | None,
    success: bool,
    detail: dict[str, Any] | None,
) -> str:
    """Deterministic serialisation. Key order is fixed so hashes reproduce."""
    return json.dumps(
        {
            "event_uid": event_uid,
            "event_type": event_type,
            "actor_uid": actor_uid,
            "actor_role": actor_role,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "resource_hash": resource_hash,
            "success": success,
            "detail": detail or {},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _head_hash(db: Session) -> str:
    row = db.execute(
        select(AuditEvent.event_hash).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()
    return row or GENESIS_HASH


def record(
    db: Session,
    *,
    event_type: str,
    actor: User | None = None,
    resource_type: str = "SYSTEM",
    resource_id: str = "-",
    resource_hash: str | None = None,
    success: bool = True,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
    blockchain_tx: str | None = None,
) -> AuditEvent:
    """Append one event to the chain.

    The caller is responsible for committing; this participates in the caller's
    transaction so an audit entry can never be committed for work that rolled back.
    """
    event_uid = f"EVT-{uuid.uuid4().hex[:16].upper()}"
    prev_hash = _head_hash(db)
    payload = _canonical_payload(
        event_uid=event_uid,
        event_type=event_type,
        actor_uid=actor.user_uid if actor else None,
        actor_role=actor.role.value if actor else None,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_hash=resource_hash,
        success=success,
        detail=detail,
    )
    event_hash = sha256_hex(prev_hash + payload)

    event = AuditEvent(
        event_uid=event_uid,
        event_type=event_type,
        actor_id=actor.id if actor else None,
        actor_role=actor.role.value if actor else None,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_hash=resource_hash,
        success=success,
        detail=json.dumps(detail or {}, sort_keys=True),
        ip_address=ip_address,
        prev_hash=prev_hash,
        event_hash=event_hash,
        blockchain_tx=blockchain_tx,
    )
    db.add(event)
    db.flush()
    return event


def recompute_hash(event: AuditEvent, actor_uid: str | None) -> str:
    """Recompute an event's hash from its stored fields."""
    payload = _canonical_payload(
        event_uid=event.event_uid,
        event_type=event.event_type,
        actor_uid=actor_uid,
        actor_role=event.actor_role,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        resource_hash=event.resource_hash,
        success=event.success,
        detail=json.loads(event.detail) if event.detail else {},
    )
    return sha256_hex(event.prev_hash + payload)


def verify_chain(db: Session) -> dict[str, Any]:
    """Walk the whole chain and report the first break, if any.

    Returns a structure the Audit dashboard renders directly.
    """
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    uid_by_id = {u.id: u.user_uid for u in db.execute(select(User)).scalars().all()}

    expected_prev = GENESIS_HASH
    broken: list[dict[str, Any]] = []

    for event in events:
        actor_uid = uid_by_id.get(event.actor_id) if event.actor_id else None
        issues = []
        if event.prev_hash != expected_prev:
            issues.append("BROKEN_LINK")
        if recompute_hash(event, actor_uid) != event.event_hash:
            issues.append("CONTENT_MODIFIED")
        if issues:
            broken.append(
                {
                    "event_uid": event.event_uid,
                    "event_type": event.event_type,
                    "issues": issues,
                    "expected_prev_hash": expected_prev,
                    "stored_prev_hash": event.prev_hash,
                    "stored_event_hash": event.event_hash,
                    "recomputed_event_hash": recompute_hash(event, actor_uid),
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
            )
        expected_prev = event.event_hash

    return {
        "total_events": len(events),
        "intact": not broken,
        "broken_count": len(broken),
        "first_broken_at": broken[0]["event_uid"] if broken else None,
        "broken_events": broken,
        "chain_head": expected_prev,
    }


def chain_head(db: Session) -> str:
    return _head_hash(db)
