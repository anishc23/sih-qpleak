"""Exam, synthesis and paper routes, including the time lock."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import client_ip, current_user, require_roles
from app.models import (
    Exam,
    ExamBlueprint,
    Paper,
    PaperStatus,
    Question,
    QuestionStatus,
    QuestionVariation,
    Role,
    User,
)
from app.schemas import (
    ExamCreate,
    ExamOut,
    GeneratePaperRequest,
    PaperContentOut,
    PaperDetailOut,
    PaperOut,
    PaperQuestionOut,
    RegisterPaperRequest,
)
from app.services import papers as paper_service
from app.services.blockchain import blockchain
from app.services.papers import PaperError
from app.services.questions import decrypt_for_system
from app.services.synthesis import (
    build_vectors,
    candidates_from_questions,
    find_duplicates,
)

router = APIRouter(tags=["exams & papers"])


# ----------------------------------------------------------------------
# Exams
# ----------------------------------------------------------------------


def serialize_exam(exam: Exam) -> ExamOut:
    bp = exam.blueprint
    return ExamOut(
        exam_uid=exam.exam_uid,
        title=exam.title,
        subject=exam.subject,
        total_marks=exam.total_marks,
        question_count=exam.question_count,
        scheduled_at=exam.scheduled_at,
        blueprint=(
            {
                "difficulty_distribution": json.loads(bp.difficulty_distribution),
                "topic_distribution": json.loads(bp.topic_distribution),
                "type_distribution": json.loads(bp.type_distribution) if bp.type_distribution else None,
            }
            if bp
            else None
        ),
        paper_count=len(exam.papers),
        created_at=exam.created_at,
    )


@router.post("/exams", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    exam = Exam(
        exam_uid=f"EXAM-{uuid.uuid4().hex[:8].upper()}",
        title=payload.title,
        subject=payload.subject,
        total_marks=payload.total_marks,
        question_count=payload.question_count,
        scheduled_at=payload.scheduled_at,
        created_by=user.id,
    )
    db.add(exam)
    db.flush()
    db.add(
        ExamBlueprint(
            exam_id=exam.id,
            difficulty_distribution=json.dumps(payload.blueprint.difficulty_distribution),
            topic_distribution=json.dumps(payload.blueprint.topic_distribution),
            type_distribution=(
                json.dumps(payload.blueprint.type_distribution)
                if payload.blueprint.type_distribution
                else None
            ),
        )
    )
    db.commit()
    db.refresh(exam)
    return serialize_exam(exam)


@router.get("/exams", response_model=list[ExamOut])
def list_exams(db: Session = Depends(get_db), _: User = Depends(current_user)):
    exams = db.execute(select(Exam).order_by(Exam.id.desc())).scalars().all()
    return [serialize_exam(e) for e in exams]


def _get_exam(db: Session, exam_uid: str) -> Exam:
    exam = db.execute(select(Exam).where(Exam.exam_uid == exam_uid)).scalar_one_or_none()
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No exam {exam_uid}.")
    return exam


# ----------------------------------------------------------------------
# Synthesis
# ----------------------------------------------------------------------


@router.get("/synthesis/duplicates")
def duplicate_analysis(
    subject: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.EXAM_AUTHORITY, Role.REVIEWER, Role.SUPER_ADMIN)),
):
    """Run TF-IDF similarity over the approved pool.

    Real similarity detection, computed on the spot. Nothing here calls a hosted
    model, and the numbers are reproducible.
    """
    stmt = select(Question).where(
        Question.status.in_(
            [QuestionStatus.AVAILABLE_FOR_SYNTHESIS, QuestionStatus.APPROVED]
        )
    )
    if subject:
        stmt = stmt.where(Question.subject == subject)
    rows = db.execute(stmt).scalars().all()

    candidates = candidates_from_questions((q, decrypt_for_system(q)) for q in rows)
    build_vectors(candidates)
    pairs = find_duplicates(candidates, settings.duplicate_similarity_threshold)
    return {
        "pool_size": len(candidates),
        "threshold": settings.duplicate_similarity_threshold,
        "method": "TF-IDF + cosine similarity",
        "pairs": [p.as_dict() for p in pairs[:100]],
        "high_risk": sum(1 for p in pairs if p.risk == "HIGH"),
    }


@router.get("/synthesis/variations")
def list_variations(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.REVIEWER, Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    rows = db.execute(
        select(QuestionVariation, Question)
        .join(Question, Question.id == QuestionVariation.question_id)
        .order_by(QuestionVariation.id.desc())
        .limit(100)
    ).all()
    out = []
    for variation, question in rows:
        from app.security.crypto import decrypt
        from app.security.keyvault import decrypt_key

        out.append(
            {
                "id": variation.id,
                "question_uid": question.question_uid,
                "original": decrypt_for_system(question),
                "variation": decrypt(
                    variation.encrypted_content, decrypt_key(variation.wrapped_key, "question")
                ),
                "similarity_score": round(variation.similarity_score, 4),
                "generation_method": variation.generation_method,
                "review_status": variation.review_status,
                "original_hash": variation.original_hash,
                "generated_hash": variation.generated_hash,
                "topic": question.topic,
                "difficulty": question.difficulty.value,
            }
        )
    return out


@router.post("/synthesis/variations/{variation_id}/review")
def review_variation(
    variation_id: int,
    approve: bool,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.REVIEWER, Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    """A generated variation never reaches a paper without a human decision."""
    from app.services import audit
    from app.services.audit import EventType

    variation = db.get(QuestionVariation, variation_id)
    if variation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such variation.")
    variation.review_status = "APPROVED" if approve else "REJECTED"
    variation.reviewed_by = user.id
    audit.record(
        db,
        event_type=EventType.VARIATION_APPROVED,
        actor=user,
        resource_type="QUESTION",
        resource_id=str(variation.question_id),
        resource_hash=variation.generated_hash,
        success=approve,
        detail={"decision": variation.review_status},
    )
    db.commit()
    return {"id": variation.id, "review_status": variation.review_status}


# ----------------------------------------------------------------------
# Papers
# ----------------------------------------------------------------------


def serialize_paper(paper: Paper, *, detail: bool = False):
    base = {
        "paper_uid": paper.paper_uid,
        "exam_uid": paper.exam.exam_uid,
        "exam_title": paper.exam.title,
        "status": paper.status,
        "paper_hash": paper.paper_hash,
        "release_time": paper.release_time,
        "released_at": paper.released_at,
        "contract_address": paper.contract_address,
        "registration_tx": paper.registration_tx,
        "release_tx": paper.release_tx,
        "question_count": len(paper.questions),
        "blueprint_compliance": json.loads(paper.blueprint_compliance)
        if paper.blueprint_compliance
        else None,
        "synthesis_report": json.loads(paper.synthesis_report)
        if paper.synthesis_report
        else None,
        "created_at": paper.created_at,
    }
    if not detail:
        return PaperOut(**base)
    return PaperDetailOut(
        **base,
        questions=[
            PaperQuestionOut(
                sequence=item.sequence,
                question_uid=item.question.question_uid,
                topic=item.question.topic,
                difficulty=item.question.difficulty,
                marks=item.marks,
                selection_score=item.selection_score,
                selection_reason=item.selection_reason,
                used_variation=item.used_variation,
            )
            for item in paper.questions
        ],
    )


def _get_paper(db: Session, paper_uid: str) -> Paper:
    paper = db.execute(select(Paper).where(Paper.paper_uid == paper_uid)).scalar_one_or_none()
    if paper is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No paper {paper_uid}.")
    return paper


@router.post("/exams/{exam_uid}/generate-paper", response_model=PaperDetailOut)
def generate_paper(
    exam_uid: str,
    payload: GeneratePaperRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    exam = _get_exam(db, exam_uid)
    try:
        paper = paper_service.generate_paper(
            db,
            authority=user,
            exam=exam,
            apply_variations=payload.apply_variations,
            ip_address=client_ip(request),
        )
    except PaperError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(paper)
    return serialize_paper(paper, detail=True)


@router.get("/papers", response_model=list[PaperOut])
def list_papers(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.execute(select(Paper).order_by(Paper.id.desc())).scalars().all()
    return [serialize_paper(p) for p in rows]


@router.get("/papers/{paper_uid}", response_model=PaperDetailOut)
def get_paper(paper_uid: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return serialize_paper(_get_paper(db, paper_uid), detail=True)


@router.post("/papers/{paper_uid}/encrypt", response_model=PaperOut)
def encrypt_paper(
    paper_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    paper = _get_paper(db, paper_uid)
    try:
        paper_service.approve_and_encrypt(
            db, authority=user, paper=paper, ip_address=client_ip(request)
        )
    except PaperError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    db.refresh(paper)
    return serialize_paper(paper)


@router.post("/papers/{paper_uid}/register-blockchain")
def register_blockchain(
    paper_uid: str,
    payload: RegisterPaperRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.EXAM_AUTHORITY, Role.SUPER_ADMIN)),
):
    paper = _get_paper(db, paper_uid)

    # The lock is evaluated against block.timestamp, so the window is measured
    # from the chain's clock. On a local dev chain that can sit well ahead of
    # wall-clock time; measuring from the server clock would silently produce a
    # release time the contract considers to be in the past.
    try:
        chain_now = blockchain.chain_time()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Cannot read blockchain time, so the lock cannot be armed: {exc}",
        ) from exc

    if payload.release_in_seconds is not None:
        release_timestamp = chain_now + payload.release_in_seconds
    elif payload.release_time is not None:
        release_time = payload.release_time
        if release_time.tzinfo is None:
            release_time = release_time.replace(tzinfo=timezone.utc)
        release_timestamp = int(release_time.timestamp())
        if release_timestamp <= chain_now:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"That release time is already in the past by blockchain time "
                f"(chain clock reads {chain_now}). Choose a later time.",
            )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide either release_time or release_in_seconds.",
        )

    try:
        result = paper_service.register_on_chain(
            db,
            authority=user,
            paper=paper,
            release_timestamp=release_timestamp,
            ip_address=client_ip(request),
        )
    except PaperError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    return result


@router.get("/papers/{paper_uid}/time-lock")
def time_lock(paper_uid: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Lock state from the contract, plus the server clock for the demo comparison."""
    paper = _get_paper(db, paper_uid)
    state = paper_service.time_lock_status(paper)
    state["server_time"] = int(datetime.now(timezone.utc).timestamp())
    state["paper_uid"] = paper.paper_uid
    return state


@router.post("/papers/{paper_uid}/release")
def release(
    paper_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    paper = _get_paper(db, paper_uid)
    try:
        result = paper_service.release_paper(
            db, actor=user, paper=paper, ip_address=client_ip(request)
        )
    except PaperError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    return result


@router.post("/papers/{paper_uid}/decrypt", response_model=PaperContentOut)
def decrypt_paper(
    paper_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """The endpoint the demo attacks directly.

    It re-checks the contract itself, so calling it with curl -- bypassing the
    UI entirely -- is refused exactly the same way.
    """
    paper = _get_paper(db, paper_uid)
    try:
        content = paper_service.decrypt_paper(
            db, actor=user, paper=paper, ip_address=client_ip(request)
        )
    except PaperError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    db.commit()
    return PaperContentOut(
        paper_uid=paper.paper_uid,
        content=content,
        paper_hash=paper.paper_hash or "",
        released_at=paper.released_at,
        blockchain_verified=True,
    )


@router.get("/papers/{paper_uid}/verify")
def verify_paper(paper_uid: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return paper_service.verify_paper_integrity(_get_paper(db, paper_uid))
