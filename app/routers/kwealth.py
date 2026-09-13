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
USER_BOOKS_DIR = Path("app/static/uploads/kwealth_books")
USER_BOOKS_DIR.mkdir(parents=True, exist_ok=True)
USER_BOOKS_TEXT = Path("app/static/uploads/kwealth_books_text")
USER_BOOKS_TEXT.mkdir(parents=True, exist_ok=True)

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



def _extract_pdf_pages(data: bytes) -> list:
    """Extract text pages from a PDF; fall back to one page if empty."""
    pages = []
    try:
        from pypdf import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(data))
        for i, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if not text:
                text = f"(Page {i+1} — little or no extractable text. Scanned PDFs may need OCR.)"
            pages.append(text)
    except Exception as e:
        pages = [f"(Could not read PDF: {e})"]
    return pages or ["(Empty PDF)"]


def _extract_txt_pages(data: bytes) -> list:
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = data.decode("latin-1", errors="ignore")
    return _split_pages(text)


@router.post("/member/kwealth/books/upload")
async def upload_device_books(
    files: list[UploadFile] = File(...),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Load PDF/TXT books from the member's device (file picker), scan, and add to library."""
    if not files:
        raise HTTPException(400, "No files selected")
    added = 0
    for f in files:
        if not f.filename:
            continue
        name = f.filename
        ext = (name.rsplit(".", 1)[-1] or "").lower()
        if ext not in ("pdf", "txt", "text"):
            continue
        data = await f.read()
        if not data or len(data) > 40 * 1024 * 1024:
            continue
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]
        uid = uuid.uuid4().hex[:10]
        if ext == "pdf":
            pages = _extract_pdf_pages(data)
            bin_path = USER_BOOKS_DIR / f"{user.id}_{uid}_{safe}"
            bin_path.write_bytes(data)
            text_rel = f"uploads/kwealth_books_text/{user.id}_{uid}.txt"
            text_path = Path("app/static") / text_rel
            text_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n\n".join(f"Page {i+1}\n{p}" for i, p in enumerate(pages))
            text_path.write_text(body, encoding="utf-8")
            source_path = text_rel
        else:
            pages = _extract_txt_pages(data)
            text_rel = f"uploads/kwealth_books_text/{user.id}_{uid}_{safe}"
            if not text_rel.endswith(".txt"):
                text_rel += ".txt"
            text_path = Path("app/static") / text_rel
            text_path.parent.mkdir(parents=True, exist_ok=True)
            body = "\n\n".join(f"Page {i+1}\n{p}" for i, p in enumerate(pages))
            text_path.write_text(body, encoding="utf-8")
            source_path = text_rel

        title = name.rsplit(".", 1)[0].replace("_", " ").strip()[:120] or "Book"
        session.add(KwealthBook(
            title=title,
            author=f"Uploaded by member {user.id}",
            source_path=source_path,
            page_count=len(pages),
            is_active=True,
        ))
        added += 1
    session.commit()
    return RedirectResponse(f"/member/kwealth/books?uploaded={added}", status_code=303)


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


@router.get("/member/kwealth/notes/api/list")
async def notes_list_api(user: User = Depends(require_user), session: Session = Depends(get_session)):
    notes = session.exec(
        select(KwealthNote).where(KwealthNote.user_id == user.id).order_by(KwealthNote.updated_at.desc())
    ).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body_text or "",
            "ink": n.ink_path or "",
            "updated_at": n.updated_at.isoformat() if n.updated_at else "",
        }
        for n in notes
    ]


@router.post("/member/kwealth/notes")
async def save_note(
    title: str = Form(""),
    body_text: str = Form(""),
    note_id: str = Form(""),
    ink: UploadFile = File(None),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    ink_path = None
    if ink and ink.filename:
        data = await ink.read()
        if len(data) < 5_000_000:
            fname = f"ink_{user.id}_{uuid.uuid4().hex[:10]}.png"
            dest = INK_DIR / fname
            dest.write_bytes(data)
            ink_path = f"/static/uploads/kwealth_ink/{fname}"

    nid = None
    try:
        nid = int(note_id) if note_id else None
    except Exception:
        nid = None

    note = session.get(KwealthNote, nid) if nid else None
    if note and note.user_id != user.id:
        note = None

    if note:
        note.title = (title or "").strip() or note.title or "Note"
        note.body_text = (body_text or "").strip() or None
        if ink_path:
            note.ink_path = ink_path
        note.updated_at = datetime.utcnow()
        session.add(note)
    else:
        note = KwealthNote(
            user_id=user.id,
            title=(title or "").strip() or "Note",
            body_text=(body_text or "").strip() or None,
            ink_path=ink_path,
        )
        session.add(note)
    session.commit()
    session.refresh(note)
    return JSONResponse({"ok": True, "id": note.id, "title": note.title})


@router.post("/member/kwealth/notes/{note_id}/delete")
async def delete_note(note_id: int, user: User = Depends(require_user), session: Session = Depends(get_session)):
    note = session.get(KwealthNote, note_id)
    if note and note.user_id == user.id:
        session.delete(note)
        session.commit()
    return JSONResponse({"ok": True})


@router.get("/member/api/badge-count")
async def badge_count(user: User = Depends(require_user), session: Session = Depends(get_session)):
    """Unread-ish activity count for PWA / app icon badge."""
    count = 0
    try:
        from app.models import Announcement
        anns = session.exec(select(Announcement).where(Announcement.is_active == True)).all()
        count += min(len(anns or []), 9)
    except Exception:
        pass
    try:
        # best-effort message unread
        from app import models as M
        Message = getattr(M, "Message", None) or getattr(M, "DirectMessage", None)
        if Message is not None:
            q = select(Message)
            rows = session.exec(q).all()
            for m in rows:
                rid = getattr(m, "recipient_id", None) or getattr(m, "to_user_id", None)
                if rid == user.id and not getattr(m, "is_read", True):
                    count += 1
    except Exception:
        pass
    return JSONResponse({"count": int(count)})


@router.post("/member/api/angel-ask")
async def angel_ask(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Angel answers from Bible themes, Matthew Henry framing, and saved excerpts only."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = (data.get("question") or data.get("q") or "").strip()
    if not q:
        return JSONResponse({"ok": False, "answer": "How may I help you?"})

    excerpts = session.exec(
        select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id).order_by(KwealthExcerpt.created_at.desc()).limit(40)
    ).all()
    ql = q.lower()
    words = [w for w in re.findall(r"[a-z']{3,}", ql) if w not in (
        "what", "does", "mean", "about", "tell", "please", "from", "the", "and", "how", "can", "you", "with", "that", "this", "have", "when", "where", "why", "who", "angel"
    )]

    matched = []
    for e in excerpts:
        blob = f"{e.title or ''} {e.body or ''} {e.source or ''}".lower()
        score = sum(1 for w in words if w in blob)
        if score:
            matched.append((score, e))
    matched.sort(key=lambda x: -x[0])

    topical = {
        "shepherd": ("the Bible (Psalm 23)", "The Lord is our shepherd. He restores the soul, leads beside still waters, and walks with us even through the valley so we need not fear."),
        "psalm 23": ("the Bible (Psalm 23)", "Psalm 23 teaches trust in the Lord as Shepherd: provision, rest, guidance, comfort, and a home in His presence forever."),
        "faith": ("the Bible", "Faith is confidence in God and His word. It comes by hearing the word of Christ, and without faith it is impossible to please God."),
        "prayer": ("the Bible", "Prayer is talking with God in faith: ask, seek, and knock; be anxious for nothing, but in everything by prayer and thanksgiving make your requests known to God."),
        "jesus": ("the Bible", "Jesus is the Son of God, the Saviour. Whoever believes in Him shall not perish but have everlasting life. He is the way, the truth, and the life."),
        "holy spirit": ("the Bible", "The Holy Spirit is the Comforter who teaches, convicts, and empowers believers to live for Christ."),
        "holiness": ("the Bible", "God calls His people to be holy as He is holy. Holiness is a life set apart in love and obedience."),
        "love": ("the Bible", "Love is the greatest command: love the Lord your God, and love your neighbour as yourself. Love is patient and kind."),
        "salvation": ("the Bible", "Salvation is by grace through faith in Jesus Christ: confess Him as Lord and believe that God raised Him from the dead."),
        "creation": ("the Bible", "In the beginning God created the heavens and the earth. All things were made through Him."),
        "rapture": ("the Bible", "The Scripture teaches that the Lord will return; the dead in Christ rise first, then the living are caught up together with them."),
    }

    ref_name = None
    body = None

    if matched:
        e = matched[0][1]
        ref_name = (e.source or e.title or "your saved excerpts").strip()
        body = (e.body or "").strip()
        # compress to ~30s speech
        if len(body) > 500:
            body = body[:500].rsplit(" ", 1)[0] + "."
    else:
        for key, (rn, text) in topical.items():
            if key in ql:
                ref_name, body = rn, text
                break
        if not body and any(w in ql for w in ("bible", "scripture", "verse", "gospel", "god", "lord", "christ", "matthew", "henry", "commentary", "explain", "meaning")):
            ref_name = "Matthew Henry's commentary"
            body = (
                "Read the passage carefully in context. Henry stresses the plain sense of Scripture, "
                "Christ at the centre, and practical holiness. Seek the main truth of the text and apply it in faith and obedience."
            )

    if not body:
        return JSONResponse({"ok": True, "answer": "Sorry I can't help with that.", "outside": True})

    answer = f"According to {ref_name}, {body}"
    # hard cap ~90 words
    words_out = answer.split()
    if len(words_out) > 90:
        answer = " ".join(words_out[:90]) + "."
    return JSONResponse({"ok": True, "answer": answer, "outside": False})
