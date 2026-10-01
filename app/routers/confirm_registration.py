"""Registration email confirmation — case-sensitive tokens, 1-day trial, auto-login."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import os
import secrets
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, EmailChallenge, ChurchMember, ChurchUnit
from app.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.mailer import send_mail, branded, public_base

router = APIRouter(prefix="/auth", tags=["confirm"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

CONFIRM_HOURS = 72
TRIAL_HOURS = 24


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").strip().encode("utf-8")).hexdigest()


def _page(request: Request, **ctx):
    ctx.setdefault("request", request)
    try:
        return templates.TemplateResponse("auth/confirm_registration.html", ctx)
    except Exception:
        ok = ctx.get("ok")
        msg = ctx.get("message") or ""
        return HTMLResponse(
            f"<!DOCTYPE html><html><body style='font-family:system-ui;padding:2rem;text-align:center'>"
            f"<h1>{'Confirmed' if ok else 'Link issue'}</h1><p>{msg}</p>"
            f"<p><a href='/auth/login'>Sign in</a></p></body></html>"
        )


def _grant_one_day_trial(session: Session, user: User, member: ChurchMember | None):
    now = datetime.utcnow()
    if hasattr(user, "welcome_started_at"):
        user.welcome_started_at = now
    user.is_active = True
    session.add(user)
    if member:
        session.add(member)
    try:
        from app.models import MemberSubscription
        sub = session.exec(select(MemberSubscription).where(MemberSubscription.user_id == user.id)).first()
        ends = now + timedelta(hours=TRIAL_HOURS)
        if sub:
            sub.status = "active"
            if hasattr(sub, "ends_at"):
                sub.ends_at = ends
            session.add(sub)
        else:
            try:
                session.add(MemberSubscription(user_id=user.id, status="active", ends_at=ends, plan="welcome_trial"))
            except Exception:
                session.add(MemberSubscription(user_id=user.id, status="active"))
    except Exception as e:
        print("welcome trial:", e)
    session.commit()


def send_registration_confirm_email(session: Session, email: str, full_name: str, user_id: int | None = None) -> bool:
    token = secrets.token_urlsafe(32)
    session.add(
        EmailChallenge(
            email=(email or "").strip().lower(),
            purpose="register_confirm",
            code_hash=_hash_token(token),
            pending_user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(hours=CONFIRM_HOURS),
            used=False,
        )
    )
    session.commit()
    link = (
        f"{public_base()}/auth/confirm-registration"
        f"?email={quote(email.strip(), safe='')}&token={quote(token, safe='')}"
    )
    text = (
        f"Hello {full_name},\n\n"
        "Confirm your Knowsoft Churchgate registration:\n"
        f"{link}\n\n"
        "After confirmation, non-church affiliates get 1 day of full access, then a subscription is required.\n"
        "This link expires in 72 hours.\n"
    )
    html = branded(
        "Confirm your registration",
        f"<p>Hello <b>{full_name}</b>,</p>"
        f"<p><a href='{link}' style='background:#0d9488;color:#fff;padding:12px 20px;"
        f"border-radius:10px;text-decoration:none;font-weight:700'>Confirm my registration</a></p>"
        f"<p style='font-size:12px;word-break:break-all'>{link}</p>",
    )
    return send_mail(email.strip(), "Confirm your Knowsoft Churchgate registration", text, html)


@router.get("/confirm-registration", response_class=HTMLResponse)
async def confirm_registration(
    request: Request,
    email: str = "",
    token: str = "",
    session: Session = Depends(get_session),
):
    email = unquote((email or "").strip()).lower()
    token = unquote((token or "").strip()).replace(" ", "").replace("\n", "").replace("\r", "")

    def fail(msg: str):
        return _page(request, ok=False, message=msg, login=True, auto_approved=False)

    if not email or not token:
        return fail("This confirmation link is incomplete. Open the full link from your email.")

    try:
        rows = list(
            session.exec(
                select(EmailChallenge)
                .where(
                    EmailChallenge.email == email,
                    EmailChallenge.purpose == "register_confirm",
                )
                .order_by(EmailChallenge.id.desc())
            ).all()
        )
        th = _hash_token(token)
        th_old = hashlib.sha256(token.strip().upper().encode()).hexdigest()
        row = next((r for r in rows if r.code_hash in (th, th_old)), None)

        if not row:
            return fail(
                "This confirmation link is invalid or already used. "
                "Try signing in, or register again after the latest update."
            )
        if row.expires_at < datetime.utcnow():
            return fail("This confirmation link has expired. Please register again.")

        if not row.used:
            row.used = True
            session.add(row)

        user = session.exec(select(User).where(User.email == email)).first()
        member = None
        if user and getattr(user, "member_id", None):
            member = session.get(ChurchMember, user.member_id)
        if not member:
            member = session.exec(select(ChurchMember).where(ChurchMember.email == email)).first()

        auto_approved = False
        if member:
            g = session.get(ChurchUnit, member.global_church_id) if member.global_church_id else None
            gname = (g.name or "").lower() if g else ""
            conf = (member.confession or "").lower().replace("-", "_")
            if conf == "non_affiliate" or "knowsoft" in gname:
                member.approval_status = "approved"
                auto_approved = True
            session.add(member)

        if user:
            user.is_active = True
            session.add(user)
        session.commit()

        # Already used once before
        if row.used and row.code_hash in (th, th_old):
            # first time we just set used=True above; for true reuse the row was already used
            pass

        if user and (auto_approved or (member and (member.approval_status or "") == "approved")):
            _grant_one_day_trial(session, user, member)
            jwt = create_access_token({"sub": user.email})
            resp = RedirectResponse("/member/portal?welcome=1", status_code=303)
            resp.set_cookie(
                "access_token",
                jwt,
                httponly=True,
                samesite="lax",
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
            return resp

        return _page(
            request,
            ok=True,
            message="Confirmed, but awaiting church admin approval. You can sign in with limited access until approved.",
            trial_note="After approval you get 1 day of full access before a subscription is required.",
            login=True,
            auto_approved=False,
            login_url="/auth/login",
        )
    except Exception as e:
        print("confirm-registration error:", e)
        return fail("We could not process this link right now. Email info@knowsoft.org.uk for help.")
