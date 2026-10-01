"""Restore Angel resources room for General Admin."""
from pathlib import Path
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.auth import require_roles
from app.models import User, UserRole

router = APIRouter(tags=["angel-admin"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
RES_DIR = Path(__file__).resolve().parent.parent / "data" / "angel_resources"
RES_DIR.mkdir(parents=True, exist_ok=True)

def _list_files():
    files = []
    if RES_DIR.exists():
        for p in sorted(RES_DIR.glob("*")):
            if p.is_file() and p.suffix.lower() in (".txt", ".md"):
                files.append({"filename": p.name, "title": p.stem.replace("_", " "), "size": p.stat().st_size})
    # also bundled under app/data/angel_resources
    bundled = Path(__file__).resolve().parent.parent / "app" / "data" / "angel_resources"
    if not bundled.exists():
        bundled = Path(__file__).resolve().parent.parent / "data" / "angel_resources"
    return files

@router.get("/admin/angel-resources", response_class=HTMLResponse)
async def angel_resources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
    ok: str = "",
    err: str = "",
):
    files = _list_files()
    # try DB model
    try:
        from app.models import AngelResourceFile
        db_files = session.exec(select(AngelResourceFile)).all()
        for f in db_files:
            files.append({"filename": getattr(f, "filename", None) or getattr(f, "title", ""), "title": getattr(f, "title", ""), "size": 0})
    except Exception:
        pass
    return templates.TemplateResponse("admin/angel_resources.html", {
        "request": request, "user": user, "files": files, "ok": ok, "err": err,
    })

@router.post("/admin/angel-resources/upload")
async def angel_resources_upload(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    if not file.filename:
        return RedirectResponse("/admin/angel-resources?err=nofile", status_code=303)
    data = await file.read()
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)[:120]
    dest = RES_DIR / safe
    dest.write_bytes(data)
    try:
        from app.models import AngelResourceFile
        session.add(AngelResourceFile(title=title or safe, filename=safe, uploaded_by=user.id))
        session.commit()
    except Exception as e:
        print("angel upload db:", e)
    return RedirectResponse("/admin/angel-resources?ok=uploaded", status_code=303)
