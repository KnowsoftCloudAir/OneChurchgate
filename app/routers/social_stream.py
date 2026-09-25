"""Admin social video embeds + Facebook Page sync + member muted autoplay feed."""
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import quote
import json
import re
import urllib.request
import urllib.error

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, SocialStreamLink, AppConfig
from app.auth import require_user, role_val

router = APIRouter(tags=["social-stream"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

FB_PAGE_ID_KEY = "social_fb_page_id"
FB_PAGE_TOKEN_KEY = "social_fb_page_token"


def _is_admin(user: User) -> bool:
    rv = (role_val(user.role) if hasattr(user, "role") else str(getattr(user, "role", ""))).lower()
    return rv == "general_admin" or "general" in rv or "admin" in rv


def _cfg_get(session: Session, key: str) -> Optional[str]:
    row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
    return (row.value if row else None) or None


def _cfg_set(session: Session, key: str, value: str) -> None:
    row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
    if not row:
        row = AppConfig(key=key, value=value, updated_at=datetime.utcnow())
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    session.add(row)


def build_embed_url(platform: str, source_url: str) -> Optional[str]:
    if not source_url:
        return None
    url = source_url.strip()
    p = (platform or "").lower().strip()
    low = url.lower()

    if p == "facebook":
        return (
            "https://www.facebook.com/plugins/video.php?href="
            + quote(url, safe="")
            + "&show_text=false&width=auto&allowfullscreen=true&autoplay=true"
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
                + "?autoplay=1&mute=1&playsinline=1&rel=0&enablejsapi=1"
            )
        return None

    return None


def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "ChurchgateSocial/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def sync_facebook_page_videos(session: Session, page_id: str, token: str, limit: int = 25) -> int:
    """Pull public videos from a Facebook Page via Graph API into SocialStreamLink."""
    page_id = (page_id or "").strip()
    token = (token or "").strip()
    if not page_id or not token:
        return 0
    # Videos endpoint
    api = (
        f"https://graph.facebook.com/v19.0/{quote(page_id)}/videos"
        f"?fields=id,title,description,permalink_url,created_time,length"
        f"&limit={int(limit)}&access_token={quote(token)}"
    )
    try:
        data = _http_get_json(api)
    except Exception:
        # Fallback: published posts that are videos
        api2 = (
            f"https://graph.facebook.com/v19.0/{quote(page_id)}/posts"
            f"?fields=id,message,permalink_url,created_time,attachments{{media_type,url,target}}"
            f"&limit={int(limit)}&access_token={quote(token)}"
        )
        try:
            data = _http_get_json(api2)
        except Exception as e:
            raise HTTPException(400, f"Facebook API error: {e}")

    items = data.get("data") or []
    added = 0
    existing_urls = {
        (r.source_url or "").strip()
        for r in session.exec(select(SocialStreamLink)).all()
    }

    for it in items:
        permalink = (it.get("permalink_url") or "").strip()
        if not permalink:
            # construct from id when possible
            vid = it.get("id")
            if vid and page_id:
                permalink = f"https://www.facebook.com/{page_id}/videos/{vid}/"
        if not permalink or permalink in existing_urls:
            # also skip if already have facebook.com/video style
            continue
        # filter posts that are not video when using /posts
        atts = it.get("attachments") or {}
        att_data = (atts.get("data") or [{}])[0] if isinstance(atts, dict) else {}
        media_type = (att_data.get("media_type") or "").lower()
        if media_type and media_type not in ("video", "video_inline"):
            # if came from /videos endpoint, media_type may be absent — allow
            if "videos" not in str(it.get("id", "")) and not it.get("length"):
                continue

        title = (it.get("title") or it.get("message") or "Facebook video").strip()
        title = re.sub(r"\s+", " ", title)[:200]
        desc = (it.get("description") or it.get("message") or "").strip()[:500]
        embed = build_embed_url("facebook", permalink)
        row = SocialStreamLink(
            platform="facebook",
            title=title or "Facebook video",
            source_url=permalink[:800],
            embed_url=(embed[:900] if embed else None),
            description=desc or "Synced from Facebook Page",
            is_active=True,
            created_by=None,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        existing_urls.add(permalink)
        added += 1

    session.commit()
    return added


@router.get("/admin/social-stream", response_class=HTMLResponse)
async def admin_social_stream(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    if not _is_admin(user):
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
            "fb_page_id": _cfg_get(session, FB_PAGE_ID_KEY) or "",
            "has_token": bool(_cfg_get(session, FB_PAGE_TOKEN_KEY)),
            "synced": request.query_params.get("synced"),
        },
    )


@router.post("/admin/social-stream/facebook-page")
async def admin_save_facebook_page(
    page_id: str = Form(""),
    page_token: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")
    page_id = (page_id or "").strip()
    page_token = (page_token or "").strip()
    if page_id:
        _cfg_set(session, FB_PAGE_ID_KEY, page_id)
    if page_token:
        _cfg_set(session, FB_PAGE_TOKEN_KEY, page_token)
    session.commit()
    return RedirectResponse("/admin/social-stream?ok=fb_saved", status_code=303)


@router.post("/admin/social-stream/sync-facebook")
async def admin_sync_facebook(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")
    page_id = _cfg_get(session, FB_PAGE_ID_KEY)
    token = _cfg_get(session, FB_PAGE_TOKEN_KEY)
    if not page_id or not token:
        return RedirectResponse("/admin/social-stream?err=fb_config", status_code=303)
    try:
        n = sync_facebook_page_videos(session, page_id, token, limit=30)
    except HTTPException as e:
        return RedirectResponse(f"/admin/social-stream?err={quote(str(e.detail)[:80])}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin/social-stream?err={quote(str(e)[:80])}", status_code=303)
    return RedirectResponse(f"/admin/social-stream?ok=synced&synced={n}", status_code=303)


@router.post("/admin/social-stream/add")
async def admin_social_stream_add(
    platform: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(...),
    description: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    if not _is_admin(user):
        raise HTTPException(403, "Admin only")
    platform = (platform or "").lower().strip()
    if platform not in ("facebook", "tiktok", "instagram", "youtube"):
        return RedirectResponse("/admin/social-stream?err=platform", status_code=303)
    source_url = (source_url or "").strip()
    if not source_url.startswith("http"):
        return RedirectResponse("/admin/social-stream?err=url", status_code=303)
    embed = build_embed_url(platform, source_url)
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
    if not _is_admin(user):
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
    if not _is_admin(user):
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
