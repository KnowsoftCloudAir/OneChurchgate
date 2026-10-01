
"""Angel resources — multi file upload into AngelResourceFile.body."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import List

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


@router.get("/admin/angel-resources", response_class=HTMLResponse)
async def angel_resources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    files = []
    for row in session.exec(select(AngelResourceFile).order_by(AngelResourceFile.id.desc())).all():
        files.append({
            "id": row.id,
            "title": row.title,
            "active": row.is_active,
            "preview": (row.body or "")[:160],
            "source": "database",
        })
    for p in sorted(DISK.glob("*.txt")):
        files.append({
            "id": None,
            "title": p.stem.replace("_", " "),
            "active": True,
            "preview": p.read_text(encoding="utf-8", errors="ignore")[:160],
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
            "added": request.query_params.get("added"),
        },
    )


@router.post("/admin/angel-resources/upload")
async def angel_resources_upload(
    files: List[UploadFile] = File(None),
    file: UploadFile = File(None),
    title: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    uploads: List[UploadFile] = []
    if files:
        uploads.extend([f for f in files if f and f.filename])
    if file and file.filename:
        uploads.append(file)
    if not uploads:
        return RedirectResponse("/admin/angel-resources?err=nofile", status_code=303)

    added = 0
    for up in uploads:
        raw = await up.read()
        if not raw:
            continue
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", errors="ignore")
        if not text.strip():
            continue
        name = (title.strip() if title.strip() and len(uploads) == 1 else (up.filename or "Resource")).rsplit(".", 1)[0][:200]
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in (up.filename or "res.txt"))[:120]
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
        added += 1
    session.commit()
    if added == 0:
        return RedirectResponse("/admin/angel-resources?err=empty", status_code=303)
    return RedirectResponse(f"/admin/angel-resources?ok=uploaded&added={added}", status_code=303)


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
