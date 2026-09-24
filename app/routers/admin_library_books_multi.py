"""
Paste this route into app/routers/admin.py near the existing /library/book handler.

Requires: Path, List, UploadFile, File, Form, RedirectResponse, Session,
uuid, User, UserRole, KwealthBook, require_roles, get_session, router
"""

@router.post("/library/books")
async def admin_library_books_multi(
    files: List[UploadFile] = File(...),
    default_author: str = Form(""),
    user: User = Depends(require_roles(UserRole.general_admin)),
    session: Session = Depends(get_session),
):
    from app.routers.kwealth import _extract_text_from_upload, _split_pages
    import uuid
    here = Path(__file__).resolve().parent.parent
    out_dir = here / "static" / "uploads" / "kwealth_books_text"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    author = (default_author or "").strip()[:120] or None
    for f in files or []:
        raw = await f.read()
        if not raw or len(raw) > 20_000_000:
            continue
        text = (_extract_text_from_upload(raw, f.filename or "book.txt") or "").strip()
        if len(text) < 20:
            continue
        safe = f"ga_{uuid.uuid4().hex[:12]}.txt"
        dest = out_dir / safe
        dest.write_text(text, encoding="utf-8")
        title = (f.filename or "Book").rsplit(".", 1)[0].replace("_", " ").strip()[:180] or "Book"
        book = KwealthBook(
            title=title,
            author=author,
            source_path=str(dest),
            page_count=max(1, len(_split_pages(text))),
            is_active=True,
        )
        session.add(book)
        count += 1
    session.commit()
    if count == 0:
        return RedirectResponse("/admin/library?err=no_valid_files", status_code=303)
    return RedirectResponse(f"/admin/library?ok=books&n={count}", status_code=303)
