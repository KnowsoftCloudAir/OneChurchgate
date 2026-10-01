"""Admin: load permanent books + BGM like stream library."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session
from app.database import get_session
from app.auth import require_roles
from app.models import User, UserRole

router = APIRouter(tags=["permanent-library"])

@router.post("/admin/library/load-permanent")
async def load_permanent(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    from app.seed_permanent_books import seed_permanent_library
    r = seed_permanent_library(session, force=False)
    return RedirectResponse(
        f"/admin/kwealth-books?ok=permanent&books={r.get('books',0)}&bgm={r.get('bgm',0)}",
        status_code=303,
    )
