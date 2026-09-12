"""Kwealth: books reader, notes, excerpts + Angel knowledge helpers."""
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import re
import uuid

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session, engine
from app.models import (
    User, KwealthBook, KwealthProgress, KwealthExcerpt, KwealthNote, AngelReference,
)
from app.auth import require_user

router = APIRouter(tags=["kwealth"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
BOOKS_DIR = Path("app/static/books")
INK_DIR = Path("app/static/uploads/kwealth_ink")
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
INK_DIR.mkdir(parents=True, exist_ok=True)

MH_URL = "https://www.biblestudytools.com/commentaries/matthew-henry-complete/"
CHARS_PER_PAGE = 900


def _split_pages(text: str) -> List[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return ["(Empty book)"]
    # Prefer explicit "Page N" markers
    parts = re.split(r"\n\s*Page\s+\d+\s*\n", text, flags=re.I)
    pages = [p.strip() for p in parts if p.strip()]
    if len(pages) >= 2:
        return pages
    # Fallback: chunk by characters at paragraph boundaries
    pages = []
    buf = []
    n = 0
    for para in text.split("\n\n"):
        if n + len(para) > CHARS_PER_PAGE and buf:
            pages.append("\n\n".join(buf).strip())
            buf = [para]
            n = len(para)
        else:
            buf.append(para)
            n += len(para)
    if buf:
        pages.append("\n\n".join(buf).strip())
    return pages or [text]


def sync_books_from_disk(session: Session) -> int:
    """Load .txt books from static/books into DB."""
    added = 0
    for path in sorted(BOOKS_DIR.glob("*.txt")):
        rel = f"books/{path.name}"
        existing = session.exec(select(KwealthBook).where(KwealthBook.source_path == rel)).first()
        body = path.read_text(encoding="utf-8", errors="ignore")
        pages = _split_pages(body)
        title_line = body.split("\n", 1)[0].strip()[:120] or path.stem.replace("_", " ").title()
        if existing:
            existing.page_count = len(pages)
            existing.title = title_line
            existing.is_active = True
            session.add(existing)
        else:
            session.add(KwealthBook(
                title=title_line,
                author=None,
                source_path=rel,
                page_count=len(pages),
                is_active=True,
            ))
            added += 1
    # Ensure Matthew Henry reference row
    ref = session.exec(select(AngelReference).where(AngelReference.name == "Matthew Henry Complete")).first()
    if not ref:
        session.add(AngelReference(
            name="Matthew Henry Complete",
            url=MH_URL,
            notes="Classic whole-Bible commentary. Angel cites this for verse-by-verse questions.",
            is_active=True,
        ))
    session.commit()
    return added


def _book_pages(book: KwealthBook) -> List[str]:
    if not book.source_path:
        return ["(No file)"]
    path = Path("app/static") / book.source_path
    if not path.exists():
        path = Path(book.source_path)
    if not path.exists():
        return ["(File missing)"]
    return _split_pages(path.read_text(encoding="utf-8", errors="ignore"))


def _stats(session: Session, user: User):
    books = session.exec(select(KwealthBook).where(KwealthBook.is_active == True)).all()
    progs = session.exec(select(KwealthProgress).where(KwealthProgress.user_id == user.id)).all()
    read = sum(1 for p in progs if p.completed or p.page_index > 0)
    return len(books), read, books, progs


@router.get("/member/kwealth", response_class=HTMLResponse)
async def kwealth_home(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    try:
        sync_books_from_disk(session)
    except Exception as e:
        print("kwealth sync:", e)
    total, read, books, _ = _stats(session, user)
    excerpts_n = len(session.exec(select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id)).all())
    notes_n = len(session.exec(select(KwealthNote).where(KwealthNote.user_id == user.id)).all())
    return templates.TemplateResponse("kwealth/home.html", {
        "request": request, "user": user,
        "total_books": total, "total_read": read,
        "excerpts_n": excerpts_n, "notes_n": notes_n,
        "mh_url": MH_URL,
    })


@router.post("/member/kwealth/load-books")
async def load_books(user: User = Depends(require_user), session: Session = Depends(get_session)):
    n = sync_books_from_disk(session)
    return RedirectResponse("/member/kwealth/books", status_code=303)


@router.get("/member/kwealth/books", response_class=HTMLResponse)
async def books_page(
    request: Request,
    book_id: Optional[int] = None,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    try:
        sync_books_from_disk(session)
    except Exception as e:
        print("sync:", e)
    books = session.exec(select(KwealthBook).where(KwealthBook.is_active == True).order_by(KwealthBook.title)).all()
    book = None
    pages: List[str] = []
    page_index = 0
    if book_id:
        book = session.get(KwealthBook, book_id)
    if not book and books:
        book = books[0]
    if book:
        pages = _book_pages(book)
        prog = session.exec(
            select(KwealthProgress).where(
                KwealthProgress.user_id == user.id,
                KwealthProgress.book_id == book.id,
            )
        ).first()
        if prog:
            page_index = max(0, min(prog.page_index, len(pages) - 1))
    return templates.TemplateResponse("kwealth/books.html", {
        "request": request, "user": user, "books": books, "book": book,
        "pages": pages, "page_index": page_index, "mh_url": MH_URL,
    })


@router.post("/member/kwealth/books/progress")
async def save_progress(
    book_id: int = Form(...),
    page_index: int = Form(0),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    book = session.get(KwealthBook, book_id)
    if not book:
        raise HTTPException(404)
    pages = _book_pages(book)
    page_index = max(0, min(int(page_index), max(0, len(pages) - 1)))
    prog = session.exec(
        select(KwealthProgress).where(
            KwealthProgress.user_id == user.id,
            KwealthProgress.book_id == book_id,
        )
    ).first()
    if not prog:
        prog = KwealthProgress(user_id=user.id, book_id=book_id)
    prog.page_index = page_index
    prog.completed = page_index >= len(pages) - 1
    prog.updated_at = datetime.utcnow()
    session.add(prog)
    session.commit()
    return JSONResponse({"ok": True, "page_index": page_index})


@router.post("/member/kwealth/excerpts/from-book")
async def excerpt_from_book(
    book_id: int = Form(...),
    text: str = Form(...),
    title: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    book = session.get(KwealthBook, book_id)
    body = (text or "").strip()
    if not body:
        raise HTTPException(400, "Nothing to save")
    session.add(KwealthExcerpt(
        user_id=user.id,
        title=(title or "").strip() or (book.title if book else "Excerpt"),
        body=body[:8000],
        source=book.title if book else "Book",
    ))
    session.commit()
    return JSONResponse({"ok": True})


@router.get("/member/kwealth/excerpts", response_class=HTMLResponse)
async def excerpts_page(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id).order_by(KwealthExcerpt.created_at.desc())
    ).all()
    return templates.TemplateResponse("kwealth/excerpts.html", {
        "request": request, "user": user, "excerpts": rows, "mh_url": MH_URL,
    })


@router.post("/member/kwealth/excerpts")
async def save_excerpt(
    body: str = Form(...),
    title: str = Form(""),
    source: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    body = (body or "").strip()
    if not body:
        raise HTTPException(400, "Paste an excerpt first")
    session.add(KwealthExcerpt(
        user_id=user.id,
        title=(title or "").strip() or "Excerpt",
        body=body[:12000],
        source=(source or "").strip() or "Manual paste",
    ))
    session.commit()
    return RedirectResponse("/member/kwealth/excerpts", status_code=303)


@router.post("/member/kwealth/excerpts/{excerpt_id}/delete")
async def delete_excerpt(excerpt_id: int, user: User = Depends(require_user), session: Session = Depends(get_session)):
    row = session.get(KwealthExcerpt, excerpt_id)
    if row and row.user_id == user.id:
        session.delete(row)
        session.commit()
    return RedirectResponse("/member/kwealth/excerpts", status_code=303)


@router.get("/member/kwealth/notes", response_class=HTMLResponse)
async def notes_page(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    notes = session.exec(
        select(KwealthNote).where(KwealthNote.user_id == user.id).order_by(KwealthNote.updated_at.desc())
    ).all()
    # Build highlight dictionary from Bible keywords + excerpts + MH marker
    keys = set()
    for e in session.exec(select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id)).all():
        for w in re.findall(r"[A-Za-z']{4,}", e.body or ""):
            keys.add(w.lower())
    for phrase in ["lord", "jesus", "faith", "prayer", "shepherd", "gospel", "matthew", "henry", "commentary", "bible"]:
        keys.add(phrase)
    return templates.TemplateResponse("kwealth/notes.html", {
        "request": request, "user": user, "notes": notes,
        "highlight_words": sorted(keys)[:400],
        "mh_url": MH_URL,
    })


@router.post("/member/kwealth/notes")
async def save_note(
    title: str = Form(""),
    body_text: str = Form(""),
    ink: UploadFile = File(None),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    ink_path = None
    if ink and ink.filename:
        data = await ink.read()
        if len(data) < 3_000_000:
            fname = f"ink_{user.id}_{uuid.uuid4().hex[:10]}.png"
            dest = INK_DIR / fname
            dest.write_bytes(data)
            ink_path = f"/static/uploads/kwealth_ink/{fname}"
    note = KwealthNote(
        user_id=user.id,
        title=(title or "").strip() or "Note",
        body_text=(body_text or "").strip() or None,
        ink_path=ink_path,
    )
    session.add(note)
    session.commit()
    return RedirectResponse("/member/kwealth/notes", status_code=303)


@router.post("/member/api/angel-ask")
async def angel_ask(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Angel answers Bible questions using Matthew Henry reference + member excerpts."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = (data.get("question") or data.get("q") or "").strip()
    if not q:
        return JSONResponse({"ok": False, "answer": "Please ask a Bible question."})

    # Collect knowledge
    excerpts = session.exec(
        select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id).order_by(KwealthExcerpt.created_at.desc()).limit(30)
    ).all()
    refs = session.exec(select(AngelReference).where(AngelReference.is_active == True)).all()
    mh = next((r for r in refs if r.url and "matthew-henry" in (r.url or "")), None)
    mh_url = (mh.url if mh else MH_URL)

    ql = q.lower()
    matched = []
    for e in excerpts:
        blob = f"{e.title or ''} {e.body or ''} {e.source or ''}".lower()
        words = [w for w in re.findall(r"[a-z]{4,}", ql) if w not in ("what", "does", "mean", "about", "tell", "please", "from")]
        if any(w in blob for w in words[:8]):
            matched.append(e)

    # Detect simple Bible reference pattern
    ref_m = re.search(
        r"\b(genesis|exodus|leviticus|numbers|deuteronomy|joshua|judges|ruth|samuel|kings|chronicles|ezra|nehemiah|esther|job|psalm|psalms|proverbs|ecclesiastes|isaiah|jeremiah|ezekiel|daniel|hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|zephaniah|haggai|zechariah|malachi|matthew|mark|luke|john|acts|romans|corinthians|galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon|hebrews|james|peter|jude|revelation)\s+\d+",
        ql,
    )

    parts = []
    parts.append("I am Angel. For deeper verse-by-verse insight I use Matthew Henry's Complete Commentary.")
    if ref_m:
        bookish = ref_m.group(0).replace(" ", "-")
        parts.append(f"Open the commentary around your passage here: {mh_url}")
        parts.append(f"Search the site for: {ref_m.group(0)}.")
    else:
        parts.append(f"Matthew Henry complete commentary: {mh_url}")

    if matched:
        parts.append("From your saved excerpts:")
        for e in matched[:3]:
            snippet = (e.body or "")[:280].replace("\n", " ")
            parts.append(f"— {e.title or 'Excerpt'}: {snippet}")
    else:
        parts.append("You can save Bible or book excerpts under Kwealth → Excerpts so I can quote them when you ask.")

    # Light topical answers
    if any(w in ql for w in ("shepherd", "psalm 23", "psalm twenty")):
        parts.append("Psalm 23 comforts us that the Lord is our Shepherd — He restores the soul and walks with us in the valley.")
    if "faith" in ql:
        parts.append("Faith comes by hearing the word of God (Romans 10:17). Henry often stresses trusting God's promises in Christ.")
    if "pray" in ql or "prayer" in ql:
        parts.append("Pray with faith and perseverance. Matthew 6 and Philippians 4:6-7 are strong anchors.")

    answer = " ".join(parts)
    return JSONResponse({
        "ok": True,
        "answer": answer,
        "matthew_henry_url": mh_url,
        "matched_excerpts": len(matched),
    })
