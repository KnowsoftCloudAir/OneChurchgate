"""Angel resources room for General Admin — MUST be included in main.py."""
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

# Prefer app/data/angel_resources (bundled knowledge)
APP_ROOT = Path(__file__).resolve().parent.parent
RES_DIRS = [
    APP_ROOT / "data" / "angel_resources",
    APP_ROOT / "app" / "data" / "angel_resources",  # unlikely
]
for d in RES_DIRS:
    d.mkdir(parents=True, exist_ok=True)


def _list_files():
    files = []
    seen = set()
    for RES_DIR in RES_DIRS:
        if not RES_DIR.exists():
            continue
        for p in sorted(RES_DIR.glob("*")):
            if p.is_file() and p.suffix.lower() in (".txt", ".md") and p.name not in seen:
                seen.add(p.name)
                files.append({"filename": p.name, "title": p.stem.replace("_", " "), "size": p.stat().st_size})
    return files


@router.get("/admin/angel-resources", response_class=HTMLResponse)
async def angel_resources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    files = _list_files()
    try:
        from app.models import AngelResourceFile
        for f in session.exec(select(AngelResourceFile)).all():
            files.append({
                "filename": getattr(f, "filename", "") or "",
                "title": getattr(f, "title", "") or "",
                "size": 0,
            })
    except Exception:
        pass
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
    data = await file.read()
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in file.filename)[:120]
    dest = RES_DIRS[0] / safe
    dest.write_bytes(data)
    try:
        from app.models import AngelResourceFile
        session.add(AngelResourceFile(title=title or safe, filename=safe, uploaded_by=getattr(user, "id", None)))
        session.commit()
    except Exception as e:
        print("angel upload db:", e)
    return RedirectResponse("/admin/angel-resources?ok=uploaded", status_code=303)
