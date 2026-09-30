"""Admin social video embeds + Facebook Page sync + member muted autoplay feed."""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote, urlencode
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
GRAPH = "https://graph.facebook.com/v21.0"


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


def extract_youtube_channel_id(url: str) -> Optional[str]:
    """Return UC… channel id from common YouTube URL shapes, if present."""
    if not url:
        return None
    u = url.strip()
    m = re.search(r"youtube\.com/channel/(UC[A-Za-z0-9_-]{20,})", u)
    if m:
        return m.group(1)
    if u.startswith("ytchan:") or u.startswith("channel:"):
        cid = u.split(":", 1)[1].strip()
        if cid.startswith("UC") and len(cid) >= 22:
            return cid
    m = re.search(r"[?&]channel=(UC[A-Za-z0-9_-]{20,})", u)
    if m:
        return m.group(1)
    return None


def resolve_youtube_handle_to_channel_id(handle: str) -> Optional[str]:
    """Best-effort resolve @handle → UC… without API key (HTML scrape)."""
    handle = (handle or "").lstrip("@").strip()
    if not handle or not re.match(r"^[A-Za-z0-9._-]+$", handle):
        return None
    page = f"https://www.youtube.com/@{handle}"
    try:
        req = urllib.request.Request(
            page,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChurchgateSocial/1.2)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        for pat in (
            r'"channelId":"(UC[A-Za-z0-9_-]{20,})"',
            r'"externalId":"(UC[A-Za-z0-9_-]{20,})"',
            r"channel/(UC[A-Za-z0-9_-]{20,})",
        ):
            m = re.search(pat, html)
            if m:
                return m.group(1)
    except Exception:
        return None
    return None


def is_channel_live_embed(embed_url: Optional[str]) -> bool:
    if not embed_url:
        return False
    return "embed/live_stream" in embed_url and "channel=" in embed_url


def channel_live_embed(channel_id: str, muted: bool = True) -> str:
    cid = (channel_id or "").strip()
    mute = "1" if muted else "0"
    return (
        "https://www.youtube.com/embed/live_stream?channel="
        + quote(cid, safe="")
        + f"&autoplay=1&mute={mute}&playsinline=1&rel=0&modestbranding=1"
    )


def build_embed_url(platform: str, source_url: str) -> Optional[str]:
    """Build iframe embed URL. YouTube channel /live → persistent live_stream embed."""
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
        # Persistent channel live — e.g.
        # https://www.youtube.com/channel/UCEXGDNclvmg6RW0vipJYsTQ/live
        cid = extract_youtube_channel_id(url)
        if cid:
            return channel_live_embed(cid)

        handle = re.search(r"youtube\.com/@([A-Za-z0-9._-]+)", url)
        if handle:
            resolved = resolve_youtube_handle_to_channel_id(handle.group(1))
            if resolved:
                return channel_live_embed(resolved)
            return None

        if re.search(r"youtube\.com/(?:c|user)/[A-Za-z0-9._-]+", url) and "/live" in low:
            return None

        m = re.search(
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/"
            r"|youtube\.com/live/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
            url,
        )
        if not m:
            m = re.search(r"(?:live/|v=|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
        if m:
            vid = m.group(1)
            host = "https://www.youtube.com/embed/"
            q = "autoplay=1&mute=1&playsinline=1&rel=0&modestbranding=1&enablejsapi=1"
            return host + vid + "?" + q
        return None

    return None


def _graph_get(path: str, params: Dict[str, str]) -> Dict[str, Any]:
    qs = urlencode(params)
    url = f"{GRAPH}/{path.lstrip('?')}?{qs}" if path.startswith("?") else f"{GRAPH}/{path.lstrip('/')}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "ChurchgateSocial/1.1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body)
            msg = (err.get("error") or {}).get("message") or body
            code = (err.get("error") or {}).get("code")
            sub = (err.get("error") or {}).get("error_subcode")
            detail = f"{msg}"
            if code is not None:
                detail += f" (code {code}"
                if sub is not None:
                    detail += f"/{sub}"
                detail += ")"
        except Exception:
            detail = body[:300] or str(e)
        raise HTTPException(400, detail[:240])


def _validate_page_token(page_id: str, token: str) -> Tuple[str, str]:
    """Confirm token works; return (resolved_page_id, page_name)."""
    page_id = (page_id or "").strip()
    token = (token or "").strip()
    if not page_id or not token:
        raise HTTPException(400, "Missing Page ID or token")

    # 1) Token debug / identity
    try:
        me = _graph_get("me", {"fields": "id,name", "access_token": token})
    except HTTPException as e:
        raise HTTPException(
            400,
            "Token rejected by Facebook. Generate a Page access token in Graph API Explorer "
            f"(not only a User token). Detail: {e.detail}",
        )

    token_id = str(me.get("id") or "")
    token_name = str(me.get("name") or "")

    # If token is a Page token, /me returns the Page
    if token_id == page_id:
        return page_id, token_name or page_id

    # 2) Try reading the page with this token
    try:
        page = _graph_get(page_id, {"fields": "id,name", "access_token": token})
        return str(page.get("id") or page_id), str(page.get("name") or token_name or page_id)
    except HTTPException:
        pass

    # 3) User token path: list pages and pick matching id
    try:
        accounts = _graph_get("me/accounts", {"fields": "id,name,access_token", "access_token": token})
        for acc in accounts.get("data") or []:
            if str(acc.get("id")) == page_id and acc.get("access_token"):
                # Prefer the page token from accounts
                return page_id, str(acc.get("name") or page_id)
    except HTTPException:
        pass

    raise HTTPException(
        400,
        "Facebook rejected Page ID + token. Common causes: (1) ID is a personal profile not a Page, "
        "(2) token is a short User token without Page permissions, (3) app not connected to the Page. "
        f"Token identity id={token_id}. Open Graph API Explorer → me/accounts and use that Page access_token.",
    )


def _resolve_page_token_if_user(page_id: str, token: str) -> str:
    """If user token, exchange for page token via me/accounts."""
    try:
        accounts = _graph_get(
            "me/accounts",
            {"fields": "id,name,access_token", "access_token": token},
        )
        for acc in accounts.get("data") or []:
            if str(acc.get("id")) == str(page_id) and acc.get("access_token"):
                return str(acc["access_token"])
    except HTTPException:
        pass
    return token


def sync_facebook_page_videos(session: Session, page_id: str, token: str, limit: int = 30) -> int:
    page_id = (page_id or "").strip()
    token = (token or "").strip()
    _validate_page_token(page_id, token)
    token = _resolve_page_token_if_user(page_id, token)

    items: List[Dict[str, Any]] = []
    last_err = None

    # Try several endpoints — FB returns 400 when field/permission mismatch
    attempts = [
        (f"{page_id}/videos", {"fields": "id,title,description,permalink_url,created_time", "limit": str(limit)}),
        (f"{page_id}/videos", {"fields": "id,description,permalink_url,created_time", "limit": str(limit)}),
        (f"{page_id}/published_posts", {
            "fields": "id,message,permalink_url,created_time,attachments{media_type,url,target,media,subattachments}",
            "limit": str(limit),
        }),
        (f"{page_id}/posts", {
            "fields": "id,message,permalink_url,created_time,attachments{media_type,url,target}",
            "limit": str(limit),
        }),
        (f"{page_id}/feed", {
            "fields": "id,message,permalink_url,created_time,attachments{media_type,url,target}",
            "limit": str(limit),
        }),
    ]

    for path, fields in attempts:
        params = dict(fields)
        params["access_token"] = token
        try:
            data = _graph_get(path, params)
            batch = data.get("data") or []
            if batch:
                items = batch
                break
            # empty but success — keep trying other endpoints
            if not items:
                items = batch
        except HTTPException as e:
            last_err = e
            continue

    if not items and last_err is not None:
        raise last_err

    existing_urls = {
        (r.source_url or "").strip()
        for r in session.exec(select(SocialStreamLink)).all()
    }
    added = 0

    for it in items:
        permalink = (it.get("permalink_url") or "").strip()
        vid = str(it.get("id") or "")
        # posts ids look like PAGEID_POSTID
        if not permalink and vid:
            if "_" in vid:
                permalink = f"https://www.facebook.com/{vid.replace('_', '/posts/')}"
            else:
                permalink = f"https://www.facebook.com/{page_id}/videos/{vid}/"

        # Prefer video attachments from posts
        atts = it.get("attachments") or {}
        att_list = atts.get("data") if isinstance(atts, dict) else None
        media_type = ""
        if att_list:
            media_type = str((att_list[0] or {}).get("media_type") or "").lower()
            target = (att_list[0] or {}).get("target") or {}
            if isinstance(target, dict) and target.get("url") and not permalink:
                permalink = str(target.get("url"))

        # If from posts/feed and clearly not video, skip
        if media_type and media_type not in ("video", "video_inline", "animated_image_video"):
            # still allow if permalink contains /videos/
            if "/videos/" not in (permalink or "") and "video" not in media_type:
                continue

        if not permalink or permalink in existing_urls:
            continue

        title = (it.get("title") or it.get("message") or "Facebook video").strip()
        title = re.sub(r"\s+", " ", title)[:200]
        desc = (it.get("description") or it.get("message") or "Synced from Facebook Page").strip()[:500]
        embed = build_embed_url("facebook", permalink)
        row = SocialStreamLink(
            platform="facebook",
            title=title or "Facebook video",
            source_url=permalink[:800],
            embed_url=(embed[:900] if embed else None),
            description=desc,
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
    # Accept full profile URL and extract id=
    m = re.search(r"[?&]id=(\d+)", page_id)
    if m:
        page_id = m.group(1)
    m2 = re.search(r"facebook\.com/(\d{8,})", page_id)
    if m2 and not page_id.isdigit():
        page_id = m2.group(1)
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
        return RedirectResponse(
            "/admin/social-stream?err=" + quote(str(e.detail)[:180]),
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(
            "/admin/social-stream?err=" + quote(str(e)[:180]),
            status_code=303,
        )
    return RedirectResponse(f"/admin/social-stream?ok=synced&synced={n}", status_code=303)


@router.post("/admin/social-stream/add")
async def admin_social_stream_add(
    platform: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(...),
    description: str = Form(""),
    category: str = Form("tv"),
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
    cat = (category or "tv").strip().lower()
    if cat not in ("tv","movies","news","games","ministration","others"):
        cat = "tv"
    ycid = extract_youtube_channel_id(source_url)
    if not ycid and embed:
        ycid = extract_youtube_channel_id(embed)
    if platform == "youtube" and not embed:
        return RedirectResponse(
            "/admin/social-stream?err=yt_channel",
            status_code=303,
        )
    row = SocialStreamLink(
        platform=platform,
        title=(title or (platform.title() + " video")).strip()[:200],
        category=cat,
        source_url=source_url[:800],
        embed_url=(embed[:900] if embed else None),
        description=(description or "").strip()[:500] or None,
        youtube_channel_id=(ycid[:40] if ycid else None),
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
    cat = (request.query_params.get("cat") or "all").strip().lower()
    if cat not in ("all", "tv", "movies", "news", "games", "ministration", "others"):
        cat = "all"
    links = list(
        session.exec(
            select(SocialStreamLink)
            .where(SocialStreamLink.is_active == True)  # noqa: E712
            .order_by(SocialStreamLink.sort_order, SocialStreamLink.id.desc())
        ).all()
    )
    playable = []
    for L in links:
        emb = getattr(L, "embed_url", None) or ""
        src_u = getattr(L, "source_url", None) or ""
        ycid = getattr(L, "youtube_channel_id", None) or extract_youtube_channel_id(src_u)
        if ycid and (getattr(L, "platform", "") or "").lower() in ("youtube", ""):
            emb = channel_live_embed(ycid)
            try:
                L.embed_url = emb
            except Exception:
                pass
        elif not emb:
            emb = build_embed_url(getattr(L, "platform", "") or "youtube", src_u) or ""
            try:
                L.embed_url = emb
            except Exception:
                pass
        if not emb or "undefined" in emb or emb.strip() in ("", "#"):
            continue
        lc = (getattr(L, "category", None) or "").lower() or "tv"
        if cat != "all" and lc != cat:
            continue
        playable.append(L)
    return templates.TemplateResponse(
        "members/social_watch.html",
        {"request": request, "user": user, "links": playable, "cat": cat},
    )
