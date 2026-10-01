
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import Session
from app.database import get_session
from app.auth import require_roles
from app.models import User, UserRole

router = APIRouter(tags=["permanent-library"])

@router.get("/admin/library/load-permanent")
@router.post("/admin/library/load-permanent")
async def load_permanent(
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(UserRole.general_admin)),
):
    from app.seed_permanent_books import seed_permanent_library
    r = seed_permanent_library(session, force=True)
    return RedirectResponse(
        f"/admin/kwealth/books?uploaded={r.get('books',0)}&permanent=1",
        status_code=303,
    )
