"""Paper assembly, encryption, blockchain registration and time-locked release.

The critical property: `decrypt_paper` will not return plaintext unless the
smart contract has actually transitioned the paper to RELEASED. The backend does
not consult its own clock to make that decision, and neither does the browser.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Exam,
    Paper,
    PaperQuestion,
    PaperStatus,
    Question,
    QuestionStatus,
    QuestionVariation,
    Role,
    User,
)
from app.security.crypto import DecryptionError, content_hash, decrypt, encrypt, sha256_hex
from app.security.keyvault import create_wrapped_key, decrypt_key
from app.services import audit, permissions
from app.services.audit import EventType
from app.services.blockchain import BlockchainUnavailable, ReleaseDenied, blockchain
from app.services.questions import CHAIN_LIFECYCLE, decrypt_for_system
from app.services.synthesis import (
    Blueprint,
    candidates_from_questions,
    generate_variation,
    make_engine,
    variation_similarity,
)


class PaperError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def next_paper_uid(db: Session) -> str:
    count = db.execute(select(func.count(Paper.id))).scalar_one()
    year = datetime.now(timezone.utc).year
    return f"PAPER-{year}-{count + 1:03d}"


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------


def generate_paper(
    db: Session, *, authority: User, exam: Exam, apply_variations: bool = True,
    ip_address: str | None = None,
) -> Paper:
    if authority.role not in {Role.EXAM_AUTHORITY, Role.SUPER_ADMIN}:
        raise PaperError("Only the Exam Authority may generate a paper.", 403)
    if exam.blueprint is None:
        raise PaperError("This exam has no blueprint. Define one before generating a paper.")

    pool_rows = (
        db.execute(
            select(Question).where(
                Question.status == QuestionStatus.AVAILABLE_FOR_SYNTHESIS,
                Question.subject == exam.subject,
            )
        )
        .scalars()
        .all()
    )
    if len(pool_rows) < exam.question_count:
        raise PaperError(
            f"Question pool too small: {len(pool_rows)} approved questions available, "
            f"{exam.question_count} required. Approve more questions first."
        )

    candidates = candidates_from_questions((q, decrypt_for_system(q)) for q in pool_rows)
    blueprint = Blueprint.from_model(exam, exam.blueprint)
    engine = make_engine(settings.synthesis_seed, settings.duplicate_similarity_threshold)
    result = engine.select(candidates, blueprint)

    paper = Paper(
        paper_uid=next_paper_uid(db),
        exam_id=exam.id,
        status=PaperStatus.DRAFT,
        created_by=authority.id,
        blueprint_compliance=json.dumps(result.compliance),
        synthesis_report=json.dumps(
            {
                **result.report,
                "duplicates": [d.as_dict() for d in result.duplicates[:25]],
            }
        ),
    )
    db.add(paper)
    db.flush()

    by_id = {q.id: q for q in pool_rows}
    for index, candidate in enumerate(result.selected, start=1):
        question = by_id[candidate.question_id]
        used_variation = False

        if apply_variations:
            variation_text, method = generate_variation(
                candidate.text, question_type=candidate.question_type
            )
            if variation_text.strip() != candidate.text.strip():
                similarity = variation_similarity(candidate.text, variation_text)
                dek, wrapped = create_wrapped_key("question")
                db.add(
                    QuestionVariation(
                        question_id=question.id,
                        original_hash=question.content_hash,
                        generated_hash=content_hash(variation_text),
                        encrypted_content=encrypt(variation_text, dek),
                        wrapped_key=wrapped,
                        similarity_score=similarity,
                        generation_method=method,
                        review_status="PENDING",
                    )
                )
                used_variation = True
                audit.record(
                    db,
                    event_type=EventType.VARIATION_GENERATED,
                    actor=authority,
                    resource_type="QUESTION",
                    resource_id=question.question_uid,
                    resource_hash=content_hash(variation_text),
                    detail={"method": method, "similarity": round(similarity, 4)},
                    ip_address=ip_address,
                )

        db.add(
            PaperQuestion(
                paper_id=paper.id,
                question_id=question.id,
                sequence=index,
                marks=question.marks,
                selection_score=result.scores.get(candidate.question_uid, 0.0),
                selection_reason=result.reasons.get(candidate.question_uid, "")[:500],
                used_variation=used_variation,
            )
        )
        question.status = QuestionStatus.SELECTED
        blockchain.set_lifecycle(
            db,
            question_uid=question.question_uid,
            lifecycle=CHAIN_LIFECYCLE[QuestionStatus.SELECTED],
            actor_uid=authority.user_uid,
        )
        audit.record(
            db,
            event_type=EventType.QUESTION_SELECTED,
            actor=authority,
            resource_type="QUESTION",
            resource_id=question.question_uid,
            resource_hash=question.content_hash,
            detail={"paper": paper.paper_uid, "sequence": index},
            ip_address=ip_address,
        )

    paper.status = PaperStatus.PENDING_APPROVAL
    audit.record(
        db,
        event_type=EventType.PAPER_GENERATED,
        actor=authority,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        detail={
            "exam": exam.exam_uid,
            "questions": len(result.selected),
            "pool_size": len(candidates),
            "compliance": result.compliance,
        },
        ip_address=ip_address,
    )
    return paper


# ----------------------------------------------------------------------
# Rendering, encryption, registration
# ----------------------------------------------------------------------


def render_paper(db: Session, paper: Paper) -> str:
    """Assemble the printable paper. Held in memory only, never persisted plain."""
    exam = paper.exam
    lines = [
        "=" * 70,
        exam.title.upper(),
        "=" * 70,
        f"Subject      : {exam.subject}",
        f"Total Marks  : {exam.total_marks}",
        f"Questions    : {len(paper.questions)}",
        f"Paper ID     : {paper.paper_uid}",
        "",
        "Answer all questions. Marks are indicated against each question.",
        "-" * 70,
        "",
    ]
    for item in paper.questions:
        text = decrypt_for_system(item.question)
        lines.append(f"Q{item.sequence}. [{item.marks} marks] ({item.question.topic}, "
                     f"{item.question.difficulty.value.lower()})")
        lines.append(f"     {text}")
        lines.append("")
    lines.append("-" * 70)
    lines.append("END OF PAPER")
    return "\n".join(lines)


def approve_and_encrypt(
    db: Session, *, authority: User, paper: Paper, ip_address: str | None = None
) -> Paper:
    if authority.role not in {Role.EXAM_AUTHORITY, Role.SUPER_ADMIN}:
        raise PaperError("Only the Exam Authority may approve a paper.", 403)
    if paper.status not in {PaperStatus.DRAFT, PaperStatus.PENDING_APPROVAL}:
        raise PaperError(f"A {paper.status.value} paper cannot be approved again.")

    plaintext = render_paper(db, paper)
    dek, wrapped = create_wrapped_key("paper")
    ciphertext = encrypt(plaintext, dek)

    # The paper hash anchors the *encrypted artifact*, so integrity can be
    # checked without anyone decrypting anything.
    digest = sha256_hex(ciphertext)

    paper.encrypted_content = ciphertext
    paper.wrapped_key = wrapped
    paper.paper_hash = digest
    paper.status = PaperStatus.ENCRYPTED

    audit.record(
        db,
        event_type=EventType.PAPER_APPROVED,
        actor=authority,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        ip_address=ip_address,
    )
    audit.record(
        db,
        event_type=EventType.PAPER_ENCRYPTED,
        actor=authority,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        resource_hash=digest,
        detail={"algorithm": "AES-256-GCM", "bytes": len(ciphertext)},
        ip_address=ip_address,
    )
    # The plaintext local variable goes out of scope here. It was never written
    # to the database, to disk, or to a log.
    return paper


def register_on_chain(
    db: Session,
    *,
    authority: User,
    paper: Paper,
    release_timestamp: int,
    ip_address: str | None = None,
) -> dict:
    """Arm the time lock.

    `release_timestamp` is a unix time in the CHAIN's frame of reference. The
    caller resolves it from `blockchain.chain_time()`, because the contract
    compares against `block.timestamp` and nothing else.
    """
    if paper.status != PaperStatus.ENCRYPTED:
        raise PaperError("Encrypt the paper before registering it on chain.")
    if paper.paper_hash is None:
        raise PaperError("Paper has no hash.")

    release_ts = int(release_timestamp)
    release_time = datetime.fromtimestamp(release_ts, tz=timezone.utc)
    result = blockchain.register_paper(
        db,
        paper_uid=paper.paper_uid,
        paper_hash=paper.paper_hash,
        exam_uid=paper.exam.exam_uid,
        release_time=release_ts,
        actor_uid=authority.user_uid,
    )
    if not result.ok:
        audit.record(
            db,
            event_type=EventType.PAPER_REGISTERED,
            actor=authority,
            resource_type="PAPER",
            resource_id=paper.paper_uid,
            success=False,
            detail={"error": result.error},
            ip_address=ip_address,
        )
        raise PaperError(
            f"Blockchain registration failed, so the paper is NOT time locked: {result.error}",
            503,
        )

    paper.release_time = release_time
    paper.status = PaperStatus.LOCKED
    paper.registration_tx = result.tx_hash
    paper.contract_address = settings.paper_contract_address

    audit.record(
        db,
        event_type=EventType.PAPER_REGISTERED,
        actor=authority,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        resource_hash=paper.paper_hash,
        detail={"release_time": release_time.isoformat(), "contract": paper.contract_address},
        blockchain_tx=result.tx_hash,
        ip_address=ip_address,
    )
    audit.record(
        db,
        event_type=EventType.PAPER_TIME_LOCKED,
        actor=authority,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        detail={"release_time_unix": release_ts},
        blockchain_tx=result.tx_hash,
        ip_address=ip_address,
    )
    return {
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "contract_address": paper.contract_address,
        "release_time": release_time.isoformat(),
    }


# ----------------------------------------------------------------------
# The time lock
# ----------------------------------------------------------------------


def time_lock_status(paper: Paper) -> dict:
    """Lock state as reported by the chain. The UI countdown renders from this."""
    if paper.status in {PaperStatus.DRAFT, PaperStatus.PENDING_APPROVAL, PaperStatus.ENCRYPTED}:
        return {
            "registered": False,
            "status": paper.status.value,
            "message": "Paper is not yet registered on the blockchain.",
        }
    try:
        state = blockchain.time_lock_state(paper.paper_uid)
    except Exception as exc:
        return {
            "registered": True,
            "blockchain_available": False,
            "error": str(exc),
            "status": paper.status.value,
            "message": "Blockchain node unavailable - lock state cannot be confirmed.",
        }
    return {
        "registered": True,
        "blockchain_available": True,
        "status": "RELEASED" if state["released"] else "LOCKED",
        "paper_hash": state["paper_hash"],
        "release_time": state["release_time"],
        "blockchain_time": state["blockchain_time"],
        "release_time_reached": state["release_time_reached"],
        "seconds_remaining": state["seconds_remaining"],
        "released": state["released"],
        "authority": "smart-contract",
        "note": "Countdown is cosmetic. Release is decided by block.timestamp.",
    }


def release_paper(
    db: Session, *, actor: User, paper: Paper, ip_address: str | None = None
) -> dict:
    """Ask the contract to release. Denial here is the demo's headline moment."""
    decision = permissions.can_view_paper_content(actor)
    if not decision:
        raise PaperError(decision.reason, 403)
    if paper.status not in {PaperStatus.LOCKED, PaperStatus.RELEASED}:
        raise PaperError("This paper is not registered under a time lock.")

    audit.record(
        db,
        event_type=EventType.RELEASE_ATTEMPTED,
        actor=actor,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        ip_address=ip_address,
    )

    if paper.status == PaperStatus.RELEASED:
        return {"released": True, "tx_hash": paper.release_tx, "already_released": True}

    try:
        result = blockchain.release_paper(
            db, paper_uid=paper.paper_uid, actor_uid=actor.user_uid
        )
    except (ReleaseDenied, BlockchainUnavailable) as exc:
        audit.record(
            db,
            event_type=EventType.RELEASE_DENIED,
            actor=actor,
            resource_type="PAPER",
            resource_id=paper.paper_uid,
            success=False,
            detail={"reason": str(exc)},
            ip_address=ip_address,
        )
        db.commit()
        raise PaperError(str(exc), 423 if isinstance(exc, ReleaseDenied) else 503) from exc

    paper.status = PaperStatus.RELEASED
    paper.released_at = datetime.now(timezone.utc)
    paper.release_tx = result.tx_hash
    for item in paper.questions:
        item.question.status = QuestionStatus.USED_IN_PAPER

    audit.record(
        db,
        event_type=EventType.PAPER_RELEASED,
        actor=actor,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        resource_hash=paper.paper_hash,
        blockchain_tx=result.tx_hash,
        ip_address=ip_address,
    )
    return {
        "released": True,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "already_released": False,
    }


def decrypt_paper(
    db: Session, *, actor: User, paper: Paper, ip_address: str | None = None
) -> str:
    """Return paper plaintext -- only after the chain confirms release.

    Note the order: the chain is consulted BEFORE the key is unwrapped. There is
    no code path that unwraps the key on a locked paper.
    """
    decision = permissions.can_view_paper_content(actor)
    if not decision:
        audit.record(
            db,
            event_type=EventType.RELEASE_DENIED,
            actor=actor,
            resource_type="PAPER",
            resource_id=paper.paper_uid,
            success=False,
            detail={"reason": decision.reason},
            ip_address=ip_address,
        )
        db.commit()
        raise PaperError(decision.reason, 403)

    if paper.encrypted_content is None or paper.wrapped_key is None:
        raise PaperError("This paper has not been encrypted yet.")

    # Authoritative check, straight from the contract.
    try:
        state = blockchain.time_lock_state(paper.paper_uid)
    except Exception as exc:
        raise PaperError(
            f"Cannot verify the release condition because the blockchain is unreachable: {exc}. "
            "Decryption is refused.",
            503,
        ) from exc

    if not state["released"]:
        audit.record(
            db,
            event_type=EventType.RELEASE_DENIED,
            actor=actor,
            resource_type="PAPER",
            resource_id=paper.paper_uid,
            success=False,
            detail={
                "reason": "Smart contract has not released this paper.",
                "blockchain_time": state["blockchain_time"],
                "release_time": state["release_time"],
                "seconds_remaining": state["seconds_remaining"],
            },
            ip_address=ip_address,
        )
        db.commit()
        raise PaperError(
            "Decryption blocked. The smart contract has not released this paper. "
            f"{state['seconds_remaining']} seconds remain according to blockchain time. "
            "Changing your computer clock does not affect this check.",
            423,
        )

    try:
        dek = decrypt_key(paper.wrapped_key, "paper")
        plaintext = decrypt(paper.encrypted_content, dek)
    except DecryptionError as exc:
        audit.record(
            db,
            event_type=EventType.TAMPERING_DETECTED,
            actor=actor,
            resource_type="PAPER",
            resource_id=paper.paper_uid,
            success=False,
            detail={"error": str(exc)},
            ip_address=ip_address,
        )
        db.commit()
        raise PaperError("Paper integrity failure: ciphertext failed authentication.", 409) from exc

    audit.record(
        db,
        event_type=EventType.PAPER_DECRYPTED,
        actor=actor,
        resource_type="PAPER",
        resource_id=paper.paper_uid,
        resource_hash=paper.paper_hash,
        ip_address=ip_address,
    )
    return plaintext


def verify_paper_integrity(paper: Paper) -> dict:
    out = {
        "paper_uid": paper.paper_uid,
        "stored_hash": paper.paper_hash,
        "recomputed_hash": None,
        "database_consistent": None,
        "blockchain_match": None,
        "blockchain_available": True,
        "verdict": "UNKNOWN",
    }
    if paper.encrypted_content is not None:
        recomputed = sha256_hex(paper.encrypted_content)
        out["recomputed_hash"] = recomputed
        out["database_consistent"] = recomputed == paper.paper_hash

    try:
        out["blockchain_match"] = blockchain.verify_paper_hash(
            paper.paper_uid, paper.paper_hash or ""
        )
    except Exception as exc:
        out["blockchain_available"] = False
        out["blockchain_error"] = str(exc)

    if out["database_consistent"] and out["blockchain_match"]:
        out["verdict"] = "VERIFIED"
    elif out["database_consistent"] is False or out["blockchain_match"] is False:
        out["verdict"] = "PAPER_INTEGRITY_FAILURE"
    else:
        out["verdict"] = "UNVERIFIED_CHAIN_OFFLINE"
    return out
