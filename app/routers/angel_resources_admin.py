"""Angel resources repository — stores text in AngelResourceFile.body for Angel to use."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.auth import require_roles
from app.models import User, UserRole, AngelResourceFile

router = APIRouter(tags=["angel-admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
DISK = Path(__file__).resolve().parent.parent / "data" / "angel_resources"
DISK.mkdir(parents=True, exist_ok=True)
BUNDLED = Path(__file__).resolve().parent.parent / "data" / "angel_resources"


@router.get("/admin/angel-resources", response_class=HTMLResponse)
async def angel_resources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    files = []
    # DB uploads
    for row in session.exec(select(AngelResourceFile).order_by(AngelResourceFile.id.desc())).all():
        files.append({
            "id": row.id,
            "title": row.title,
            "filename": "",
            "active": row.is_active,
            "preview": (row.body or "")[:120],
            "source": "database",
        })
    # Bundled disk files (read-only list)
    for folder in (DISK, Path(__file__).resolve().parent.parent / "app" / "data" / "angel_resources"):
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.txt")):
            files.append({
                "id": None,
                "title": p.stem.replace("_", " "),
                "filename": p.name,
                "active": True,
                "preview": p.read_text(encoding="utf-8", errors="ignore")[:120],
                "source": "disk",
            })
    return templates.TemplateResponse(
        "admin/angel_resources.html",
        {
            "request": request,
            "user": user,
            "files": files,
            "ok": request.query_params.get("ok"),
            "err": request.query_params.get("err"),
        },
    )


@router.post("/admin/angel-resources/upload")
async def angel_resources_upload(
    file: UploadFile = File(...),
    title: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    if not file.filename:
        return RedirectResponse("/admin/angel-resources?err=nofile", status_code=303)
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except Exception:
        text = raw.decode("latin-1", errors="ignore")
    if not text.strip():
        return RedirectResponse("/admin/angel-resources?err=empty", status_code=303)
    name = (title or file.filename or "Resource").strip()[:200]
    # save disk copy
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)[:120]
    (DISK / safe).write_bytes(raw)
    row = AngelResourceFile(
        title=name,
        body=text,
        is_active=True,
        created_by=getattr(user, "id", None),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    return RedirectResponse("/admin/angel-resources?ok=uploaded", status_code=303)


@router.post("/admin/angel-resources/{file_id}/delete")
async def angel_resources_delete(
    file_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    row = session.get(AngelResourceFile, file_id)
    if row:
        session.delete(row)
        session.commit()
    return RedirectResponse("/admin/angel-resources?ok=deleted", status_code=303)


@router.post("/admin/angel-resources/{file_id}/toggle")
async def angel_resources_toggle(
    file_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    row = session.get(AngelResourceFile, file_id)
    if row:
        row.is_active = not row.is_active
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.commit()
    return RedirectResponse("/admin/angel-resources?ok=toggled", status_code=303)
