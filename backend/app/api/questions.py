"""Question routes: create, read (decrypt), edit, submit, review, permissions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import client_ip, current_user, require_roles
from app.models import (
    Question,
    QuestionPermission,
    QuestionStatus,
    QuestionVersion,
    Role,
    User,
)
from app.schemas import (
    ChainReceipt,
    PermissionGrant,
    PermissionsOut,
    QuestionContentOut,
    QuestionCreate,
    QuestionCreatedOut,
    QuestionOut,
    QuestionUpdate,
    ReviewRequest,
    VersionOut,
)
from app.services import audit, permissions
from app.services.audit import EventType
from app.services.questions import QuestionError, verify_integrity
from app.services import questions as question_service

router = APIRouter(prefix="/questions", tags=["questions"])


def serialize(db: Session, question: Question, viewer: User) -> QuestionOut:
    return QuestionOut(
        question_uid=question.question_uid,
        subject=question.subject,
        topic=question.topic,
        difficulty=question.difficulty,
        question_type=question.question_type,
        marks=question.marks,
        learning_objective=question.learning_objective,
        content_hash=question.content_hash,
        version=question.version,
        status=question.status,
        creator_uid=question.creator.user_uid,
        creator_name=question.creator.name,
        created_at=question.created_at,
        updated_at=question.updated_at,
        approved_at=question.approved_at,
        permissions=PermissionsOut(**permissions.summarize(db, viewer, question)),
    )


def _get(db: Session, question_uid: str) -> Question:
    question = db.execute(
        select(Question).where(Question.question_uid == question_uid)
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No question {question_uid}.")
    return question


@router.post("", response_model=QuestionCreatedOut, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.QUESTION_SETTER, Role.SUPER_ADMIN)),
):
    try:
        question, chain = question_service.create_question(
            db,
            creator=user,
            content=payload.content,
            subject=payload.subject,
            topic=payload.topic,
            difficulty=payload.difficulty,
            question_type=payload.question_type,
            marks=payload.marks,
            learning_objective=payload.learning_objective,
            ip_address=client_ip(request),
        )
    except QuestionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(question)
    return QuestionCreatedOut(
        question=serialize(db, question, user),
        encryption={
            "algorithm": "AES-256-GCM",
            "key_length_bits": 256,
            "hash_algorithm": "SHA-256",
            "content_hash": question.content_hash,
            "ciphertext_bytes": len(question.encrypted_content),
            "key_storage": "wrapped under master key; never stored bare",
        },
        blockchain=ChainReceipt(**chain),
    )


@router.get("", response_model=list[QuestionOut])
def list_questions(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    status_filter: QuestionStatus | None = Query(default=None, alias="status"),
    subject: str | None = None,
    topic: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Question)
    scope = permissions.visible_questions_filter(user)
    if scope is not None:
        stmt = stmt.where(scope)
    if status_filter:
        stmt = stmt.where(Question.status == status_filter)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if topic:
        stmt = stmt.where(Question.topic == topic)

    rows = db.execute(
        stmt.order_by(Question.id.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [serialize(db, q, user) for q in rows]


@router.get("/{question_uid}", response_model=QuestionOut)
def get_question(
    question_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """Metadata only. Content requires an explicit, audited read."""
    return serialize(db, _get(db, question_uid), user)


@router.post("/{question_uid}/read", response_model=QuestionContentOut)
def read_question(
    question_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Decrypt and return content. POST, not GET, because this is a state change:
    it produces an access log entry and an on-chain event."""
    question = _get(db, question_uid)
    try:
        content = question_service.read_question_content(
            db, reader=user, question=question, ip_address=client_ip(request)
        )
    except QuestionError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    return QuestionContentOut(
        question_uid=question.question_uid,
        content=content,
        content_hash=question.content_hash,
        version=question.version,
        access_recorded=True,
    )


@router.put("/{question_uid}", response_model=QuestionOut)
def update_question(
    question_uid: str,
    payload: QuestionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    question = _get(db, question_uid)
    try:
        question, _chain = question_service.update_question(
            db,
            editor=user,
            question=question,
            content=payload.content,
            change_note=payload.change_note,
            ip_address=client_ip(request),
            subject=payload.subject,
            topic=payload.topic,
            difficulty=payload.difficulty,
            question_type=payload.question_type,
            marks=payload.marks,
            learning_objective=payload.learning_objective,
        )
    except QuestionError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(question)
    return serialize(db, question, user)


@router.post("/{question_uid}/submit", response_model=QuestionOut)
def submit_question(
    question_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    question = _get(db, question_uid)
    try:
        question_service.submit_question(
            db, actor=user, question=question, ip_address=client_ip(request)
        )
    except QuestionError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(question)
    return serialize(db, question, user)


@router.post("/{question_uid}/review", response_model=QuestionOut)
def review_question(
    question_uid: str,
    payload: ReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    question = _get(db, question_uid)
    try:
        question_service.review_question(
            db,
            reviewer=user,
            question=question,
            approve=payload.approve,
            comment=payload.comment,
            ip_address=client_ip(request),
        )
    except QuestionError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(question)
    return serialize(db, question, user)


@router.get("/{question_uid}/versions", response_model=list[VersionOut])
def question_versions(
    question_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    question = _get(db, question_uid)
    rows = db.execute(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question.id)
        .order_by(QuestionVersion.version)
    ).scalars().all()
    return [VersionOut.model_validate(v) for v in rows]


@router.get("/{question_uid}/permissions")
def get_permissions(
    question_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    question = _get(db, question_uid)
    grants = db.execute(
        select(QuestionPermission, User)
        .join(User, User.id == QuestionPermission.user_id)
        .where(QuestionPermission.question_id == question.id)
    ).all()
    return {
        "question_uid": question.question_uid,
        "your_permissions": permissions.summarize(db, user, question),
        "explicit_grants": [
            {
                "user_uid": u.user_uid,
                "name": u.name,
                "role": u.role.value,
                "can_read": g.can_read,
                "can_write": g.can_write,
                "can_approve": g.can_approve,
            }
            for g, u in grants
        ],
    }


@router.put("/{question_uid}/permissions")
def set_permissions(
    question_uid: str,
    payload: PermissionGrant,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    decision = permissions.can_manage_permissions(user)
    if not decision:
        raise HTTPException(status.HTTP_403_FORBIDDEN, decision.reason)

    question = _get(db, question_uid)
    target = db.execute(
        select(User).where(User.user_uid == payload.user_uid)
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No user {payload.user_uid}.")

    grant = db.execute(
        select(QuestionPermission).where(
            QuestionPermission.question_id == question.id,
            QuestionPermission.user_id == target.id,
        )
    ).scalar_one_or_none()
    if grant is None:
        grant = QuestionPermission(
            question_id=question.id, user_id=target.id, granted_by=user.id
        )
        db.add(grant)
    grant.can_read = payload.can_read
    grant.can_write = payload.can_write
    grant.can_approve = payload.can_approve
    grant.granted_by = user.id

    audit.record(
        db,
        event_type=EventType.PERMISSION_GRANTED,
        actor=user,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        detail={
            "target": target.user_uid,
            "read": payload.can_read,
            "write": payload.can_write,
            "approve": payload.can_approve,
        },
        ip_address=client_ip(request),
    )
    db.commit()
    return {
        "question_uid": question.question_uid,
        "user_uid": target.user_uid,
        "can_read": grant.can_read,
        "can_write": grant.can_write,
        "can_approve": grant.can_approve,
    }


@router.get("/{question_uid}/verify")
def verify_question(
    question_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    """Recompute the hash and compare it with the on-chain anchor."""
    question = _get(db, question_uid)
    result = verify_integrity(db, question)
    audit.record(
        db,
        event_type=(
            EventType.INTEGRITY_VERIFIED
            if result["verdict"] == "VERIFIED"
            else EventType.TAMPERING_DETECTED
        ),
        actor=user,
        resource_type="QUESTION",
        resource_id=question.question_uid,
        resource_hash=question.content_hash,
        success=result["verdict"] == "VERIFIED",
        detail={"verdict": result["verdict"]},
    )
    db.commit()
    return result


@router.get("/{question_uid}/access-log")
def access_log(
    question_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    from app.models import QuestionAccessLog

    question = _get(db, question_uid)
    rows = db.execute(
        select(QuestionAccessLog, User)
        .join(User, User.id == QuestionAccessLog.user_id)
        .where(QuestionAccessLog.question_id == question.id)
        .order_by(QuestionAccessLog.id.desc())
        .limit(200)
    ).all()
    return [
        {
            "access_type": log.access_type.value,
            "granted": log.granted,
            "reason": log.reason,
            "user_uid": u.user_uid,
            "user_name": u.name,
            "role": u.role.value,
            "created_at": log.created_at,
        }
        for log, u in rows
    ]
