from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD, SESSION_COOKIE_NAME, SESSION_DAYS
from ..db import get_db
from ..models import AuditEvent, User, UserAccessToken

PBKDF2_ITERATIONS = 220_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_email(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not password or not stored_hash:
        return False
    try:
        algorithm, iterations, salt, expected_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected_hex)
    except Exception:
        return False


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def log_event(db: Session, *, user_id: str | None, event_type: str, summary: str | None = None, request: Request | None = None) -> None:
    try:
        ip_address = request.client.host if request is not None and request.client else None
        user_agent = request.headers.get("user-agent") if request is not None else None
        db.add(
            AuditEvent(
                event_id=f"evt_{uuid4().hex[:16]}",
                user_id=user_id,
                event_type=event_type,
                event_summary=summary,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
    except Exception:
        # Audit logging should never block the product flow in MVP.
        pass


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    preferred_reward_type: str | None = None,
    is_admin: bool = False,
    request: Request | None = None,
) -> User:
    email_norm = normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValueError("Enter a valid email address.")
    if db.query(User).filter(User.email == email_norm).first():
        raise ValueError("An account already exists with this email.")
    user = User(
        user_id=f"usr_{uuid4().hex[:16]}",
        email=email_norm,
        email_hash=hash_email(email_norm),
        full_name=(full_name or "").strip() or email_norm.split("@")[0],
        password_hash=hash_password(password),
        is_admin=is_admin,
        status="active",
        country="IN",
        preferred_reward_type=preferred_reward_type or "cashback",
        consent_status="manual_upload_only",
        notes="Created from CardPilot signup.",
    )
    db.add(user)
    db.flush()
    log_event(db, user_id=user.user_id, event_type="user_registered", summary="User created account", request=request)
    db.commit()
    db.refresh(user)
    return user



def set_user_password(db: Session, *, user: User, new_password: str, changed_by_user_id: str | None = None, request: Request | None = None) -> None:
    """Set a new password hash for a user. The plaintext password is never stored or returned."""
    user.password_hash = hash_password(new_password)
    log_event(
        db,
        user_id=user.user_id,
        event_type="password_reset_by_admin" if changed_by_user_id and changed_by_user_id != user.user_id else "password_changed",
        summary=f"Password updated by {changed_by_user_id or 'system'}",
        request=request,
    )
    db.commit()
    db.refresh(user)

def authenticate_user(db: Session, *, email: str, password: str, request: Request | None = None) -> User | None:
    user = db.query(User).filter(User.email == normalize_email(email), User.status == "active").first()
    if not user or not verify_password(password, user.password_hash):
        return None
    user.last_login_at = utcnow()
    log_event(db, user_id=user.user_id, event_type="user_login", summary="Successful login", request=request)
    db.commit()
    db.refresh(user)
    return user


def ensure_default_admin(db: Session) -> User:
    email_norm = normalize_email(ADMIN_EMAIL)
    admin = db.query(User).filter(User.email == email_norm).first()
    if admin:
        changed = False
        if not admin.is_admin:
            admin.is_admin = True
            changed = True
        if not admin.password_hash:
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            changed = True
        if changed:
            db.commit()
            db.refresh(admin)
        return admin
    admin = User(
        user_id=f"adm_{uuid4().hex[:16]}",
        email=email_norm,
        email_hash=hash_email(email_norm),
        full_name=ADMIN_NAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
        status="active",
        country="IN",
        preferred_reward_type="cashback",
        consent_status="admin",
        notes="Default local admin account. Change credentials before public deployment.",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def create_access_token(db: Session, user: User, *, token_name: str = "web-session", days: int = SESSION_DAYS) -> str:
    raw = f"cp_{secrets.token_urlsafe(40)}"
    row = UserAccessToken(
        token_id=f"tok_{uuid4().hex[:16]}",
        user_id=user.user_id,
        token_hash=token_hash(raw),
        token_name=token_name,
        expires_at=utcnow() + timedelta(days=days),
    )
    db.add(row)
    db.commit()
    return raw


def get_user_from_token(db: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    row = db.query(UserAccessToken).filter(UserAccessToken.token_hash == token_hash(raw_token), UserAccessToken.revoked_at.is_(None)).first()
    if not row:
        return None
    if row.expires_at is not None and row.expires_at <= utcnow():
        return None
    user = db.get(User, row.user_id)
    if not user or user.status != "active":
        return None
    row.last_used_at = utcnow()
    db.commit()
    return user


def current_user_from_request(request: Request, db: Session) -> User | None:
    user = get_user_from_token(db, request.cookies.get(SESSION_COOKIE_NAME))
    if user:
        return user
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return get_user_from_token(db, auth_header.split(" ", 1)[1].strip())
    return None


def revoke_token(db: Session, raw_token: str | None) -> bool:
    if not raw_token:
        return False
    row = db.query(UserAccessToken).filter(UserAccessToken.token_hash == token_hash(raw_token), UserAccessToken.revoked_at.is_(None)).first()
    if not row:
        return False
    row.revoked_at = utcnow()
    db.commit()
    return True


# Dependency aliases used by the optional mobile API router.
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return user


def revoke_bearer_token(db: Session, raw_token: str | None) -> bool:
    return revoke_token(db, raw_token)


def migrate_auth_schema_if_needed(db: Session) -> None:
    """Add auth columns/tables to older local SQLite databases packaged before CardPilot v1.4."""
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return
    user_cols = {row[1] for row in db.execute(text("PRAGMA table_info(users)")).fetchall()}
    additions = {
        "email": "ALTER TABLE users ADD COLUMN email TEXT",
        "full_name": "ALTER TABLE users ADD COLUMN full_name TEXT",
        "password_hash": "ALTER TABLE users ADD COLUMN password_hash TEXT",
        "is_admin": "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0",
        "status": "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'",
        "last_login_at": "ALTER TABLE users ADD COLUMN last_login_at DATETIME",
    }
    for col, sql in additions.items():
        if col not in user_cols:
            db.execute(text(sql))
    db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL"))
    db.commit()
