"""Member feature access: 5-minute welcome trial, then lock without a paid subscription."""
from datetime import datetime

from sqlmodel import Session, select

from app.auth import role_val
from app.models import MemberSubscription, User

TRIAL_MINUTES = 5
OPEN_PREFIXES = (
    "/member/subscription",
    "/auth/",
    "/static/",
    "/legal/",
)


def features_open(session: Session, user: User) -> bool:
    """Staff always open. Members open only during trial or an active paid plan."""
    if user is None or not getattr(user, "is_active", False):
        return False
    role = role_val(getattr(user, "role", None))
    if role and role != "member":
        return True
    if getattr(user, "is_sample_account", False):
        started = getattr(user, "sample_started_at", None)
        if not started:
            return True
        return (datetime.utcnow() - started).total_seconds() < TRIAL_MINUTES * 60
    now = datetime.utcnow()
    subs = session.exec(
        select(MemberSubscription).where(MemberSubscription.user_id == user.id)
    ).all()
    for sub in subs:
        if (getattr(sub, "status", "") or "") != "active":
            continue
        ends = getattr(sub, "ends_at", None)
        if ends is None or ends > now:
            return True
    return False


def path_needs_subscription(path: str) -> bool:
    if any(path.startswith(p) for p in OPEN_PREFIXES):
        return False
    return path.startswith("/member/")
