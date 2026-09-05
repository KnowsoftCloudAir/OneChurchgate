from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from dotenv import load_dotenv
import os

from app.database import get_session
from app.models import User, UserRole

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "knowsoft-churchgate-change-this-in-production-32chars")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

def role_val(role) -> str:
    if role is None:
        return ""
    return str(getattr(role, "value", role)).lower().replace("userrole.", "")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_password_hash(password: str) -> str:
    if isinstance(password, str):
        password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_user_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """JWT bound to session_version so a new login invalidates older sessions."""
    return create_access_token(
        {"sub": user.email, "sv": int(getattr(user, "session_version", 0) or 0)},
        expires_delta=expires_delta,
    )

def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.exec(select(User).where(User.email == email)).first()

async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> Optional[User]:
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        token_sv = payload.get("sv")
    except JWTError:
        return None
    user = get_user_by_email(session, email)
    if not user or not user.is_active:
        return None
    # Single active session: token must match current session_version
    if token_sv is not None:
        current_sv = int(getattr(user, "session_version", 0) or 0)
        if int(token_sv) != current_sv:
            return None
    rv = role_val(user.role)
    # Staff always see church dashboard; members only if granted or pastor status
    if rv in ("general_admin", "church_admin", "data_officer"):
        user.can_view_church_dashboard = True
    elif rv == "member":
        # Members never see the church operational dashboard
        user.can_view_church_dashboard = False
    else:
        user.can_view_church_dashboard = False
    return user

async def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_roles(*roles: UserRole):
    async def checker(user: User = Depends(require_user)) -> User:
        rv = role_val(user.role)
        allowed = {role_val(r) for r in roles} | {"general_admin"}
        if rv not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def member_access_locked(session, user: User) -> bool:
    """True if member must pay before using resources (waiting_approval / no active sub after expiry)."""
    from app.models import ChurchMember, MemberSubscription
    from sqlmodel import select
    if not user:
        return False
    rv = role_val(user.role)
    if rv in ("general_admin", "church_admin", "data_officer"):
        return False
    if getattr(user, "is_sample_account", False):
        return False  # sample handled separately
    if rv != "member":
        return False
    mem = session.get(ChurchMember, user.member_id) if user.member_id else None
    if not mem:
        mem = session.exec(select(ChurchMember).where(ChurchMember.email == user.email)).first()
    if not mem:
        return True
    status = (mem.approval_status or "").lower()
    if status in ("pending", "rejected", "discontinued", "deactivated"):
        return status != "pending"  # pending has its own preview; lock hard rejects
    if status == "waiting_approval" or status == "waiting_subscription":
        return True
    # approved but no active subscription and had expiry → should already be waiting_approval
    active = session.exec(
        select(MemberSubscription).where(
            MemberSubscription.user_id == user.id,
            MemberSubscription.status == "active",
        )
    ).first()
    if status == "approved" and not active:
        # first-time approved before welcome runs: not locked yet
        return False
    return False
