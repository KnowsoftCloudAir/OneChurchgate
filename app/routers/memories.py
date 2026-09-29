
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, Request, File, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.auth import require_user
from app.database import get_session
from app.models import User

router = APIRouter(tags=["memories"])
templates = Jinja2Templates(directory="app/templates")
MEM_DIR = Path("app/static/uploads/memories")


@router.get("/member/memories")
async def memories_page(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    photos = []
    try:
        from app.models import MemoryPhoto
        rows = session.exec(select(MemoryPhoto).where(MemoryPhoto.user_id == user.id)).all()
        photos = [{"url": r.url, "title": r.title} for r in rows]
    except Exception:
        # folder fallback
        d = MEM_DIR / str(user.id)
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                    photos.append({"url": f"/static/uploads/memories/{user.id}/{f.name}", "title": f.stem})
    music_files = []
    bgm = Path("app/static/uploads/kwealth_bgm")
    if bgm.exists():
        for folder in [bgm / "admin_global", bgm / str(user.id)]:
            if folder.exists():
                for f in folder.iterdir():
                    if f.suffix.lower() in {".mp3", ".m4a", ".ogg", ".wav"}:
                        rel = f.relative_to(Path("app/static")).as_posix()
                        music_files.append({"title": f.stem, "url": "/static/" + rel})
    return templates.TemplateResponse("memories/album.html", {
        "request": request, "user": user, "photos": photos, "music_files": music_files,
    })


@router.post("/member/memories/upload")
async def memories_upload(files: List[UploadFile] = File(...), user: User = Depends(require_user), session: Session = Depends(get_session)):
    dest = MEM_DIR / str(user.id)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        from app.models import MemoryPhoto
    except Exception:
        MemoryPhoto = None
    for f in files or []:
        raw = await f.read()
        if not raw or len(raw) > 8_000_000:
            continue
        name = (f.filename or "pic.jpg").split("/")[-1]
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]
        path = dest / safe
        path.write_bytes(raw)
        url = f"/static/uploads/memories/{user.id}/{safe}"
        if MemoryPhoto is not None:
            try:
                session.add(MemoryPhoto(user_id=user.id, url=url, title=safe))
                session.commit()
            except Exception:
                session.rollback()
    return RedirectResponse("/member/memories", status_code=303)
