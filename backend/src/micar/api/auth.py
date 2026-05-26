"""JWT verification bridge with the Next.js frontend.

Frontend mints a short-lived HS256 JWT signed with `JWT_SHARED_SECRET` and
sends it as `Authorization: Bearer <token>` on every API call. Claims:
  - sub: email
  - name: display name
  - iss: jwt_issuer (default "micar-frontend")
  - aud: jwt_audience (default "micar-backend")
  - exp: unix epoch seconds

On first sight of a valid token whose email is in `USER_EMAIL_ALLOWLIST`,
we create the User row. Subsequent calls update `last_login_at`.
"""
from __future__ import annotations

from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from micar.compliance.audit import write_audit
from micar.config import get_settings
from micar.models import User, UserRole, session_scope
from micar.schemas import UserOut

router = APIRouter(tags=["auth"])
bearer = HTTPBearer(auto_error=True)


def _decode(token: str) -> dict:
    settings = get_settings()
    secret = settings.jwt_shared_secret.get_secret_value()
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SHARED_SECRET must be configured with at least 32 characters",
        )
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:  # ExpiredSignatureError, InvalidTokenError, ...
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc.__class__.__name__}",
        ) from exc


def _provision_or_touch(session: Session, *, email: str, name: str | None) -> User:
    settings = get_settings()
    email_norm = email.lower().strip()
    allowlist = settings.allowlisted_emails
    if not allowlist and not settings.allow_unrestricted_dev_auth:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user allowlist is not configured",
        )
    if allowlist and email_norm not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="email not allowlisted"
        )

    now = datetime.now(UTC)
    user = session.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None:
        new_id = session.execute(
            insert(User)
            .values(
                email=email_norm,
                name=name,
                role=UserRole.LAWYER.value,
                last_login_at=now,
            )
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User.id)
        ).scalar_one_or_none()
        if new_id is None:
            user = session.execute(
                select(User).where(User.email == email_norm)
            ).scalar_one()
        else:
            user = session.get(User, new_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="provisioned user could not be loaded",
                )
            write_audit(
                session,
                kind="user.provisioned",
                actor_id=user.id,
                payload={"email": email_norm},
            )
        user.last_login_at = now
        if name and not user.name:
            user.name = name
    else:
        user.last_login_at = now
        if name and not user.name:
            user.name = name
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> UserOut:
    claims = _decode(creds.credentials)
    email = claims.get("sub")
    name = claims.get("name")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing sub claim")

    with session_scope() as session:
        user = _provision_or_touch(session, email=email, name=name)
        out = UserOut.model_validate(user)
    return out


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(get_current_user)) -> UserOut:
    return user
