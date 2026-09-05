"""Activity footprint logging for General Admin reports."""
from typing import Optional
from fastapi import Request
from sqlmodel import Session
from app.models import ActivityLog, User


def client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if xf:
        return xf.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def log_activity(
    session: Session,
    *,
    user: Optional[User] = None,
    action: str,
    detail: str = "",
    request: Optional[Request] = None,
    location_hint: Optional[str] = None,
) -> None:
    try:
        ip = client_ip(request) if request else None
        ua = (request.headers.get("user-agent") if request else None) or None
        path = str(request.url.path) if request else None
        # light location hint from headers (Cloudflare / proxies) when present
        loc = location_hint
        if request and not loc:
            loc = (
                request.headers.get("cf-ipcountry")
                or request.headers.get("x-vercel-ip-country")
                or request.headers.get("x-country-code")
            )
        session.add(ActivityLog(
            user_id=user.id if user else None,
            email=user.email if user else None,
            full_name=(user.full_name if user else None) or (user.email if user else None),
            action=action,
            detail=(detail or "")[:500],
            ip_address=ip,
            user_agent=(ua or "")[:300] if ua else None,
            location_hint=loc,
            path=path,
        ))
        session.commit()
    except Exception as e:
        print("activity log:", e)
        try:
            session.rollback()
        except Exception:
            pass
