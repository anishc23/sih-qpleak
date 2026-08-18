"""Authentication routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import client_ip, current_user, require_roles
from app.models import Role, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token
from app.services import audit
from app.services.audit import EventType

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()

    # Same response for unknown account and wrong password: do not leak which.
    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            audit.record(
                db,
                event_type=EventType.USER_LOGIN_FAILED,
                actor=user,
                resource_type="USER",
                resource_id=user.user_uid,
                success=False,
                detail={"reason": "bad_password"},
                ip_address=client_ip(request),
            )
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is deactivated.")

    token, expires_in = create_access_token(
        user_uid=user.user_uid, role=user.role.value, email=user.email
    )
    audit.record(
        db,
        event_type=EventType.USER_LOGIN,
        actor=user,
        resource_type="USER",
        resource_id=user.user_uid,
        ip_address=client_ip(request),
    )
    db.commit()
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Account creation is an administrative action, never self-service.

    An open /register endpoint would let anyone mint a QUESTION_SETTER account,
    which would undo the entire access-control model.
    """
    email = payload.email.lower().strip()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered.")

    user = User(
        user_uid=f"USR-{uuid.uuid4().hex[:8].upper()}",
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        department=payload.department,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        event_type=EventType.USER_CREATED,
        actor=admin,
        resource_type="USER",
        resource_id=user.user_uid,
        detail={"role": user.role.value},
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.AUDITOR)),
):
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return [UserOut.model_validate(u) for u in users]
