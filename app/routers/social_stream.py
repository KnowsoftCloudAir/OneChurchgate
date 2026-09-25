"""Admin social video embeds + member vertical feed (Facebook, TikTok, Instagram, YouTube live/VOD)."""
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import quote
import re

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, SocialStreamLink
from app.auth import require_user, role_val

router = APIRouter(tags=["social-stream"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def build_embed_url(platform: str, source_url: str) -> Optional[str]:
    """Build official embed URL from a public post/video/live link."""
    if not source_url:
        return None
    url = source_url.strip()
    p = (platform or "").lower().strip()
    low = url.lower()

    if p == "facebook":
        return (
            "https://www.facebook.com/plugins/video.php?href="
            + quote(url, safe="")
            + "&show_text=false&width=auto&allowfullscreen=true"
        )

    if p == "tiktok":
        m = re.search(r"tiktok\.com/.*/video/(\d+)", url)
        if not m:
            m = re.search(r"tiktok\.com/.*?(\d{15,})", url)
        if m:
            return "https://www.tiktok.com/embed/v2/" + m.group(1)
        return None

    if p == "instagram":
        m = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
        if m:
            code = m.group(1)
            kind = "reel" if "/reel/" in url else "p"
            return "https://www.instagram.com/" + kind + "/" + code + "/embed"
        return None

    if p == "youtube" or "youtube.com" in low or "youtu.be" in low:
        m = re.search(
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/live/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
            url,
        )
        if m:
            vid = m.group(1)
            return (
                "https://www.youtube-nocookie.com/embed/"
                + vid
                + "?autoplay=1&mute=1&playsinline=1&rel=0"
            )
        return None

    return None


@router.get("/admin/social-stream", response_class=HTMLResponse)
async def admin_social_stream(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    rv = (role_val(user.role) if hasattr(user, "role") else str(getattr(user, "role", ""))).lower()
    if rv != "general_admin" and "general" not in rv and "admin" not in rv:
        raise HTTPException(403, "Admin only")
    links = list(
        session.exec(
            select(SocialStreamLink).order_by(SocialStreamLink.sort_order, SocialStreamLink.id.desc())
        ).all()
    )
    return templates.TemplateResponse(
        "admin/social_stream.html",
        {
            "request": request,
            "user": user,
            "links": links,
            "ok": request.query_params.get("ok"),
            "err": request.query_params.get("err"),
        },
    )


@router.post("/admin/social-stream/add")
async def admin_social_stream_add(
    platform: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(...),
    description: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    rv = (role_val(user.role) if hasattr(user, "role") else str(getattr(user, "role", ""))).lower()
    if rv != "general_admin" and "general" not in rv and "admin" not in rv:
        raise HTTPException(403, "Admin only")
    platform = (platform or "").lower().strip()
    if platform not in ("facebook", "tiktok", "instagram", "youtube"):
        return RedirectResponse("/admin/social-stream?err=platform", status_code=303)
    source_url = (source_url or "").strip()
    if not source_url.startswith("http"):
        return RedirectResponse("/admin/social-stream?err=url", status_code=303)
    embed = build_embed_url(platform, source_url)
    # Allow save even if embed is None (e.g. some Live links) — member can Open original
    row = SocialStreamLink(
        platform=platform,
        title=(title or (platform.title() + " video")).strip()[:200],
        source_url=source_url[:800],
        embed_url=(embed[:900] if embed else None),
        description=(description or "").strip()[:500] or None,
        is_active=True,
        created_by=getattr(user, "id", None),
        created_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    return RedirectResponse("/admin/social-stream?ok=1", status_code=303)


@router.post("/admin/social-stream/{link_id}/toggle")
async def admin_social_stream_toggle(
    link_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    rv = (role_val(user.role) if hasattr(user, "role") else str(getattr(user, "role", ""))).lower()
    if rv != "general_admin" and "general" not in rv and "admin" not in rv:
        raise HTTPException(403, "Admin only")
    row = session.get(SocialStreamLink, link_id)
    if not row:
        raise HTTPException(404)
    row.is_active = not bool(row.is_active)
    session.add(row)
    session.commit()
    return RedirectResponse("/admin/social-stream?ok=toggle", status_code=303)


@router.post("/admin/social-stream/{link_id}/delete")
async def admin_social_stream_delete(
    link_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    rv = (role_val(user.role) if hasattr(user, "role") else str(getattr(user, "role", ""))).lower()
    if rv != "general_admin" and "general" not in rv and "admin" not in rv:
        raise HTTPException(403, "Admin only")
    row = session.get(SocialStreamLink, link_id)
    if row:
        session.delete(row)
        session.commit()
    return RedirectResponse("/admin/social-stream?ok=del", status_code=303)


@router.get("/member/social-watch", response_class=HTMLResponse)
async def member_social_watch(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    links = list(
        session.exec(
            select(SocialStreamLink)
            .where(SocialStreamLink.is_active == True)  # noqa: E712
            .order_by(SocialStreamLink.sort_order, SocialStreamLink.id.desc())
        ).all()
    )
    return templates.TemplateResponse(
        "members/social_watch.html",
        {"request": request, "user": user, "links": links},
    )
