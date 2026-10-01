"""Angel resources — multi-file upload, list all, clear success feedback."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, SQLModel, Field, Column
from sqlalchemy import Text

from app.database import get_session, engine
from app.auth import require_roles
from app.models import User, UserRole, AngelResourceFile

router = APIRouter(tags=["angel-admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
DISK = Path(__file__).resolve().parent.parent / "data" / "angel_resources"
DISK.mkdir(parents=True, exist_ok=True)


def _ensure_table():
    try:
        SQLModel.metadata.create_all(engine, tables=[AngelResourceFile.__table__])
    except Exception as e:
        print("angel resource table:", e)


def _list_files(session: Session):
    files = []
    try:
        rows = session.exec(select(AngelResourceFile).order_by(AngelResourceFile.id.desc())).all()
        for row in rows:
            files.append({
                "id": row.id,
                "title": row.title or "Untitled",
                "active": bool(row.is_active),
                "preview": (row.body or "")[:180],
                "chars": len(row.body or ""),
                "source": "database",
                "filename": None,
            })
    except Exception as e:
        print("angel list db:", e)
    try:
        for p in sorted(DISK.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            files.append({
                "id": None,
                "title": p.stem.replace("_", " "),
                "active": True,
                "preview": text[:180],
                "chars": len(text),
                "source": "disk",
                "filename": p.name,
            })
    except Exception as e:
        print("angel list disk:", e)
    return files


@router.get("/admin/angel-resources", response_class=HTMLResponse)
async def angel_resources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    _ensure_table()
    files = _list_files(session)
    return templates.TemplateResponse(
        "admin/angel_resources.html",
        {
            "request": request,
            "user": user,
            "files": files,
            "ok": request.query_params.get("ok"),
            "err": request.query_params.get("err"),
            "added": request.query_params.get("added"),
            "count": len(files),
        },
    )


@router.post("/admin/angel-resources/upload")
async def angel_resources_upload(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
    title: str = Form(""),
):
    _ensure_table()
    form = await request.form()
    uploads = []
    for key in ("files", "file"):
        for item in form.getlist(key):
            if hasattr(item, "filename") and item.filename:
                uploads.append(item)
    if not uploads:
        return RedirectResponse("/admin/angel-resources?err=nofile", status_code=303)

    added = 0
    for up in uploads:
        try:
            raw = await up.read()
            if not raw:
                continue
            try:
                text = raw.decode("utf-8")
            except Exception:
                text = raw.decode("latin-1", errors="ignore")
            if not text.strip():
                continue
            name = title.strip() if (title.strip() and len(uploads) == 1) else (up.filename or "Resource")
            name = name.rsplit(".", 1)[0][:200]
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in (up.filename or "res.txt"))[:120]
            if not safe.lower().endswith(".txt"):
                safe = safe + ".txt"
            try:
                (DISK / safe).write_bytes(raw)
            except Exception as de:
                print("disk write:", de)
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
        except Exception as e:
            print("angel upload err:", e)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        print("angel commit:", e)
        return RedirectResponse("/admin/angel-resources?err=save_failed", status_code=303)

    if added == 0:
        return RedirectResponse("/admin/angel-resources?err=empty", status_code=303)
    return RedirectResponse(f"/admin/angel-resources?ok=uploaded&added={added}", status_code=303)


@router.post("/admin/angel-resources/{file_id}/delete")
async def angel_resources_delete(
    file_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    _ensure_table()
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
    _ensure_table()
    row = session.get(AngelResourceFile, file_id)
    if row:
        row.is_active = not row.is_active
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.commit()
    return RedirectResponse("/admin/angel-resources?ok=toggled", status_code=303)
