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

def _angel_resource_path(name: str) -> Path:
    # Resolve relative to this package so files load on Render and locally
    here = Path(__file__).resolve().parent.parent  # app/
    return here / "data" / "angel_resources" / name


def _load_topic_resource(session=None) -> str:
    parts = []
    for name in ("bible_topics_matthew_henry.txt", "angel_deep_bible_studies.txt", "deeper_life_22_doctrines_deep.txt"):
        path = _angel_resource_path(name)
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    if session is not None:
        try:
            from app.models import AngelResourceFile
            rows = session.exec(
                select(AngelResourceFile).where(AngelResourceFile.is_active == True)
            ).all()
            for r in rows:
                if r.body:
                    parts.append(f"\n\n=== {r.title} ===\n{r.body}")
        except Exception:
            pass
    return "\n\n".join(parts)



def _find_topic_block(text: str, query: str) -> tuple:
    """Return (ref_name, body, block_key) from study files matching query."""
    if not text:
        return None, None, None
    ql = (query or "").lower().strip()
    # Headers like {S1} {Q1} {A1} {D01} {DL01} {DL22}
    blocks = re.split(r"\n(?=\{[A-Za-z]*\d+\})", text)
    stop = {
        "more", "please", "tell", "about", "what", "the", "and", "from", "angel",
        "this", "that", "with", "your", "have", "does", "mean", "explain",
        "continue", "deeper", "again", "some", "info", "information", "know",
        "can", "you", "how", "why", "who", "when", "where", "say", "speak",
    }
    words = [w for w in re.findall(r"[a-z']{3,}", ql) if w not in stop]

    topic_map = {
        "god": ("godhead", "god is", "who god", "trinity"),
        "jesus": ("jesus", "christ", "son of god", "virgin"),
        "heaven": ("heaven", "new earth", "new jerusalem"),
        "hell": ("hell", "lake of fire", "second death"),
        "prayer": ("prayer",),
        "praise": ("praise", "worship"),
        "worship": ("worship", "praise"),
        "rapture": ("rapture", "caught up"),
        "sanctification": ("sanctification", "holiness", "entire sanctification"),
        "holiness": ("sanctification", "holiness"),
        "repentance": ("repentance", "repent"),
        "restitution": ("restitution",),
        "justification": ("justification", "justified"),
        "baptism": ("water baptism", "baptism"),
        "communion": ("lord's supper", "communion"),
        "spirit": ("holy ghost", "holy spirit"),
        "ghost": ("holy ghost", "holy spirit"),
        "healing": ("healing", "redemption"),
        "evangelism": ("evangelism", "soul"),
        "marriage": ("marriage",),
        "resurrection": ("resurrection",),
        "tribulation": ("tribulation", "end time", "last days"),
        "millennium": ("millennial", "millennium", "thousand"),
        "judgment": ("white throne", "judgment"),
        "bible": ("holy bible", "scripture"),
        "depravity": ("depravity", "sinfulness"),
        "sin": ("depravity", "sinfulness", "sin"),
        "salvation": ("salvation", "justification", "saved"),
        "faith": ("faith",),
        "death": ("death", "soul", "life"),
        "soul": ("soul", "death", "life"),
        "creation": ("creation", "created"),
        "satan": ("satan", "lucifer", "demon", "angel"),
        "enoch": ("enoch", "walked with god", "noah", "abraham"),
        "noah": ("noah", "enoch", "abraham"),
        "abraham": ("abraham", "walked with god"),
        "moses": ("moses",),
        "david": ("david",),
        "daniel": ("daniel",),
    }

    best = None
    best_score = 0
    best_key = None

    for b in blocks:
        if not b.strip():
            continue
        header_m = re.match(r"\{([A-Za-z]*\d+)\}([^\n]*)", b)
        header = (header_m.group(0) if header_m else b[:100]).lower()
        title = (header_m.group(2) if header_m else "").lower()
        body = b.strip()
        bl = body.lower()
        score = 0

        for w in words:
            if w in header or w in title:
                score += 8
            elif w in bl:
                score += 1
        # Strong title match: "heaven" question -> DESCRIBE HEAVEN / WHO GOD etc.
        if title:
            title_words = set(re.findall(r"[a-z']{3,}", title))
            overlap = title_words & set(words)
            if overlap:
                score += 12 * len(overlap)

        for key, aliases in topic_map.items():
            if key in ql or any(a in ql for a in aliases):
                if key in bl or any(a in bl for a in aliases) or key in header:
                    score += 8
                if any(a in header or a in title for a in aliases):
                    score += 6

        # direct phrase boosts
        phrases = [
            ("who is god", "godhead"),
            ("who god is", "godhead"),
            ("who is jesus", "jesus"),
            ("tell me about heaven", "heaven"),
            ("holy bible", "bible"),
            ("entire sanctification", "sanctification"),
            ("holy ghost", "holy ghost"),
            ("holy spirit", "holy spirit"),
            ("lord's supper", "supper"),
            ("great tribulation", "tribulation"),
            ("second coming", "second coming"),
            ("white throne", "white throne"),
            ("new heaven", "new heaven"),
            ("lake of fire", "lake of fire"),
            ("millennial", "millennial"),
            ("restitution", "restitution"),
        ]
        for phrase, hint in phrases:
            if phrase in ql and hint in bl:
                score += 10

        # Prefer multi-layer deep studies over short FAQ when scores are close
        if "LAYER 2" in body.upper():
            score += 4
        if len(body) > 1500:
            score += 2
        # If user asked mainly about heaven (not hell/judgment), prefer pure heaven blocks
        if "heaven" in ql and "hell" not in ql and "judgment" not in ql and "death" not in ql:
            if "describe heaven" in header or "{s3}" in header.replace(" ","").lower() or "heaven is god" in bl[:200]:
                score += 20
            if "LAYER 1" in body.upper() and "heaven" in header:
                score += 15
            if "judgment" in header or ("hell" in header and "heaven and hell" in header):
                score -= 10
        if score > best_score:
            best_score = score
            best = body
            best_key = header_m.group(1) if header_m else "topic"

    if not best or best_score < 1:
        return None, None, None

    # Prefer LAYER sections for progressive depth
    layers = re.split(r"\n(?=LAYER\s+\d)", best, flags=re.I)
    if len(layers) > 1:
        # keep title line + layers
        title_line = layers[0].strip()
        layer_parts = [x.strip() for x in layers[1:] if x.strip()]
        body = "\n\n".join([title_line] + layer_parts) if layer_parts else best
    else:
        body = best

    ref = "the Bible"
    if "matthew henry" in best.lower() or "HENRY" in best:
        ref = "Scripture and classic teaching"
    if "DEEPER LIFE" in best.upper() or re.search(r"\{DL\d+", best):
        ref = "biblical doctrine"
    return ref, body, best_key


def _extract_layer(body: str, depth: int) -> str:
    """Return LAYER depth text (depth 0 = Layer 1). Falls back to progressive chunks."""
    if not body:
        return ""
    numbered = []
    for m in re.finditer(r"LAYER\s+(\d+)\s*([\s\S]*?)(?=\nLAYER\s+\d+|\nEncouragement:|\n={3,}|\Z)", body, re.I):
        numbered.append((int(m.group(1)), m.group(2).strip()))
    if numbered:
        numbered.sort(key=lambda x: x[0])
        idx = min(max(depth, 0), len(numbered) - 1)
        text = numbered[idx][1]
        # append encouragement on last available layer
        if idx >= len(numbered) - 1:
            enc = re.search(r"Encouragement:\s*([\s\S]+?)(?=\n={3,}|\n\{|\Z)", body, re.I)
            if enc:
                text = text + " " + enc.group(1).strip()
        return text
    # FAQ-style: progressive paragraphs
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paras) > 1:
        idx = min(max(depth, 0), len(paras) - 1)
        # take from idx to idx+1 for some flow
        return " ".join(paras[idx:idx + 2] if idx < len(paras) - 1 else paras[idx:])
    words = body.split()
    start = depth * 80
    chunk = words[start:start + 95]
    if not chunk:
        chunk = words[max(0, len(words) - 95):]
    return " ".join(chunk)


def _clean_speak(text: str) -> str:
    clean = text or ""
    for prefix in (
        "Matthew Henry emphasis:", "Henry:", "Matthew Henry:", "Logical summary:",
        "Summary:", "Bible portions:", "Bible:", "Scripture:", "Definition:",
        "Explanation:", "Illustration:", "Doctrinal explanation:",
        "According to the Bible,", "According to Matthew Henry's commentary,",
        "According to biblical doctrine,", "According to classic teaching,",
        "According to your saved excerpts,", "According to",
        "Core truth", "Still deeper", "Deeper",
    ):
        clean = re.sub(re.escape(prefix), "", clean, flags=re.I)
    clean = re.sub(r"\{[A-Za-z]*\d+\}", "", clean)
    clean = re.sub(r"LAYER\s+\d+", "", clean, flags=re.I)
    clean = re.sub(r"[•]\s*", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    # drop lines that only cite "Cross reference"
    clean = re.sub(r"(?i)cross references?:[^.]*\.?", "", clean)
    words = clean.split()
    if len(words) > 95:
        clean = " ".join(words[:95]) + "."
    return clean


def _make_follow_up(query: str, body: str, resource: str = "", depth: int = 0) -> str:
    ql = (query or "").lower()
    bl = (body or "").lower()
    pairs = [
        (("heaven", "new earth", "new jerusalem"), "Would you like to hear more about the hope of seeing God face to face?"),
        (("rapture", "caught up"), "Shall I share more about the trumpet and the comfort this gives believers?"),
        (("jesus", "christ", "son of god", "virgin"), "Would you like to go deeper on how Jesus saves and what it means to believe in Him?"),
        (("prayer",), "Shall I also explain how Jesus taught us to pray?"),
        (("faith",), "Would you like more on how faith grows by hearing the Word?"),
        (("salvation", "saved", "grace", "justification"), "Shall I explain repentance and faith more clearly?"),
        (("holiness", "sanctif"), "Would you like a deeper word on entire sanctification for daily living?"),
        (("holy spirit", "holy ghost"), "Shall I share more about the power the Holy Spirit gives for witness?"),
        (("creation", "created"), "Would you like more on man made in the image of God?"),
        (("hell", "lake of fire"), "Shall I explain more about the second death and the way of escape in Christ?"),
        (("angel", "satan", "lucifer", "demon"), "Would you like more on the enemy's limits and final end?"),
        (("repent",), "Shall I illustrate true repentance more practically?"),
        (("baptism",), "Would you like more on why baptism follows conversion?"),
        (("marriage",), "Shall I share more on the biblical picture of marriage?"),
        (("bible", "scripture"), "Would you like more on how to use the Bible as final authority?"),
        (("godhead", "trinity", "who god"), "Shall I go deeper on the Father, Son, and Holy Spirit?"),
        (("restitution",), "Would you like practical steps on making wrongs right?"),
        (("tribulation", "last days", "end time"), "Shall I share more of Jesus' call to watch and pray?"),
        (("millennium", "thousand"), "Would you like more on Christ's peaceful reign?"),
        (("judgment", "white throne"), "Shall I explain more about the book of life?"),
        (("death", "soul", "resurrection"), "Would you like more on the hope of resurrection?"),
        (("evangelism", "soul win"), "Shall I encourage you further on personal witness?"),
        (("healing", "redemption"), "Would you like more on trusting God with both soul and body?"),
    ]
    for keys, qtext in pairs:
        if any(k in ql or k in bl for k in keys):
            return qtext
    if depth >= 2:
        return "Keep loving God, walking with Him daily, and trusting Him — would you like another topic from the Word?"
    return "Would you like me to go deeper on this from the Word?"


_LAST_TOPIC: dict = {}



CHARS_PER_PAGE = 900


def _split_pages(text: str) -> List[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return ["(Empty book)"]
    pages = []
    buf = []
    count = 0
    for para in text.split("\n"):
        line = para.strip()
        if not line:
            if buf:
                buf.append("")
            continue
        if count + len(line) > CHARS_PER_PAGE and buf:
            pages.append("\n".join(buf).strip())
            buf = [line]
            count = len(line)
        else:
            buf.append(line)
            count += len(line) + 1
    if buf:
        pages.append("\n".join(buf).strip())
    return pages or ["(Empty book)"]


def _load_book_text(book: KwealthBook) -> str:
    if book.source_path:
        # try several bases
        candidates = [
            Path(book.source_path),
            Path("app") / book.source_path.replace("app/", "", 1) if book.source_path.startswith("app/") else Path("app/static") / book.source_path,
            USER_BOOKS_TEXT / Path(book.source_path).name,
            BOOKS_DIR / Path(book.source_path).name,
        ]
        here = Path(__file__).resolve().parent.parent
        candidates.append(here / "static" / "uploads" / "kwealth_books_text" / Path(book.source_path).name)
        candidates.append(here / "static" / "books" / Path(book.source_path).name)
        for c in candidates:
            try:
                if c.exists() and c.is_file():
                    return c.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
    return ""


def _extract_text_from_upload(data: bytes, filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf") or (data[:4] == b"%PDF"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    pass
            return "\n\n".join(parts)
        except Exception:
            return data.decode("utf-8", errors="ignore")
    return data.decode("utf-8", errors="ignore")


@router.get("/member/kwealth", response_class=HTMLResponse)
async def kwealth_home(request: Request, user: User = Depends(require_user), session: Session = Depends(get_session)):
    books = session.exec(select(KwealthBook).where(KwealthBook.is_active == True)).all()
    progress = session.exec(select(KwealthProgress).where(KwealthProgress.user_id == user.id)).all()
    excerpts_n = len(session.exec(select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id)).all())
    notes_n = len(session.exec(select(KwealthNote).where(KwealthNote.user_id == user.id)).all())
    return templates.TemplateResponse("kwealth/home.html", {
        "request": request,
        "user": user,
        "total_books": len(books),
        "total_read": len(progress),
        "excerpts_n": excerpts_n,
        "notes_n": notes_n,
        "mh_url": MH_URL,
    })


@router.get("/member/kwealth/books", response_class=HTMLResponse)
async def kwealth_books(
    request: Request,
    book_id: Optional[int] = None,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    books = session.exec(select(KwealthBook).where(KwealthBook.is_active == True).order_by(KwealthBook.title)).all()
    book = None
    pages = []
    page_index = 0
    if book_id:
        book = session.get(KwealthBook, book_id)
    elif books:
        book = books[0]
    if book:
        text = _load_book_text(book)
        pages = _split_pages(text)
        prog = session.exec(
            select(KwealthProgress).where(
                KwealthProgress.user_id == user.id,
                KwealthProgress.book_id == book.id,
            )
        ).first()
        if prog:
            page_index = max(0, min(prog.page_index, len(pages) - 1))
    return templates.TemplateResponse("kwealth/books.html", {
        "request": request,
        "user": user,
        "books": books,
        "book": book,
        "pages": pages,
        "page_index": page_index,
        "mh_url": MH_URL,
    })


@router.post("/member/kwealth/books/upload")
async def kwealth_books_upload(
    files: List[UploadFile] = File(...),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    count = 0
    for f in files or []:
        raw = await f.read()
        if not raw or len(raw) > 15_000_000:
            continue
        text = _extract_text_from_upload(raw, f.filename or "book.txt")
        text = (text or "").strip()
        if len(text) < 20:
            continue
        safe = f"u{user.id}_{uuid.uuid4().hex[:10]}.txt"
        dest = USER_BOOKS_TEXT / safe
        # prefer package-relative path
        here = Path(__file__).resolve().parent.parent
        dest = here / "static" / "uploads" / "kwealth_books_text" / safe
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        title = (f.filename or "Book").rsplit(".", 1)[0][:180]
        book = KwealthBook(
            title=title,
            author=None,
            source_path=str(dest),
            page_count=len(_split_pages(text)),
            is_active=True,
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        session.add(KwealthProgress(user_id=user.id, book_id=book.id, page_index=0))
        session.commit()
        count += 1
    return RedirectResponse(f"/member/kwealth/books?uploaded={count}", status_code=303)


@router.post("/member/kwealth/books/progress")
async def kwealth_books_progress(
    book_id: int = Form(...),
    page_index: int = Form(0),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    book = session.get(KwealthBook, book_id)
    if not book:
        return JSONResponse({"ok": False})
    prog = session.exec(
        select(KwealthProgress).where(
            KwealthProgress.user_id == user.id,
            KwealthProgress.book_id == book_id,
        )
    ).first()
    if not prog:
        prog = KwealthProgress(user_id=user.id, book_id=book_id, page_index=page_index)
    else:
        prog.page_index = max(0, int(page_index))
        prog.updated_at = datetime.utcnow()
    session.add(prog)
    session.commit()
    return JSONResponse({"ok": True})


@router.post("/member/kwealth/excerpts/from-book")
async def excerpt_from_book(
    book_id: int = Form(0),
    text: str = Form(""),
    title: str = Form("Highlight"),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    body = (text or "").strip()
    if not body:
        return RedirectResponse("/member/kwealth/books", status_code=303)
    src = "book"
    if book_id:
        b = session.get(KwealthBook, book_id)
        if b:
            src = b.title
    session.add(KwealthExcerpt(
        user_id=user.id,
        title=(title or "Highlight")[:200],
        body=body[:20000],
        source=src,
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
async def excerpts_save(
    title: str = Form(""),
    body: str = Form(""),
    source: str = Form(""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    body = (body or "").strip()
    if body:
        session.add(KwealthExcerpt(
            user_id=user.id,
            title=(title or "Excerpt")[:200],
            body=body[:50000],
            source=(source or "manual")[:200],
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
    for phrase in ["lord", "jesus", "faith", "prayer", "bible"]:
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
            here = Path(__file__).resolve().parent.parent
            dest = here / "static" / "uploads" / "kwealth_ink" / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
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
    count = 0
    try:
        from app.models import Announcement
        anns = session.exec(select(Announcement).where(Announcement.is_active == True)).all()
        count += min(len(anns or []), 9)
    except Exception:
        pass
    return JSONResponse({"count": int(count)})




@router.post("/member/api/angel-ask")
async def angel_ask(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Search library by words in the user's sentence; answer with content only."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = (data.get("question") or data.get("q") or "").strip()
    topic_hint = (data.get("topic") or "").strip()
    if not q:
        return JSONResponse({"ok": True, "answer": "", "follow_up": "", "outside": True})

    ql = q.lower().strip()
    uid = user.id
    resource = _load_topic_resource(session)
    last = _LAST_TOPIC.get(uid) or {}

    # "more" continues last topic quietly
    is_more = (
        ql in ("more", "yes", "yeah", "yep", "sure", "ok", "okay", "continue", "go on", "please")
        or ql.startswith("more ")
        or "tell me more" in ql
        or "go deeper" in ql
    )
    topic_q = q
    depth = 0
    if is_more:
        topic_q = last.get("topic") or topic_hint or last.get("query") or q
        depth = int(last.get("depth") or 0) + 1

    stop = {
        "more", "please", "tell", "about", "what", "the", "and", "from", "angel",
        "this", "that", "with", "your", "have", "does", "mean", "explain",
        "continue", "deeper", "again", "some", "info", "can", "you", "how",
        "why", "who", "when", "where", "say", "speak", "want", "know", "give",
        "me", "for", "any", "just", "like", "would", "could", "should",
    }
    words = [w for w in re.findall(r"[a-z']{3,}", topic_q.lower()) if w not in stop]

    # --- gather matches from excerpts ---
    gathered = []
    excerpts = session.exec(
        select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id).order_by(KwealthExcerpt.created_at.desc()).limit(50)
    ).all()
    for e in excerpts:
        blob = f"{e.title or ''} {e.body or ''} {e.source or ''}".lower()
        score = sum(2 for w in words if w in blob)
        if score:
            gathered.append((score + 5, (e.body or "").strip()))

    # --- gather from study library (multiple blocks) ---
    if resource:
        blocks = re.split(r"\n(?=\{[A-Za-z]*\d+\})", resource)
        for b in blocks:
            if not b.strip():
                continue
            bl = b.lower()
            score = sum(1 for w in words if w in bl)
            header_m = re.match(r"\{([A-Za-z]*\d+)\}([^\n]*)", b)
            title = (header_m.group(2) if header_m else "").lower()
            for w in words:
                if w in title:
                    score += 6
            if "LAYER 2" in b.upper():
                score += 2
            if score >= 2 or (len(words) == 1 and score >= 1):
                gathered.append((score, b.strip()))

    gathered.sort(key=lambda x: -x[0])

    # use last full body on more
    if is_more and last.get("full_body"):
        body = last["full_body"]
        layer = _extract_layer(body, depth)
        answer = _clean_speak(layer)
        if not answer.strip():
            answer = _clean_speak(body)
        _LAST_TOPIC[uid] = {
            "topic": last.get("topic") or topic_q,
            "query": q,
            "depth": depth,
            "full_body": body,
            "ref": "",
            "block_key": last.get("block_key"),
        }
        return JSONResponse({
            "ok": True,
            "answer": answer,
            "follow_up": "",
            "outside": False,
            "topic": _LAST_TOPIC[uid]["topic"],
            "depth": depth,
        })

    if not gathered:
        # one more try: single best block finder
        ref_name, body, block_key = _find_topic_block(resource, topic_q)
        if body:
            gathered = [(5, body)]

    if not gathered:
        return JSONResponse({
            "ok": True,
            "answer": "",
            "follow_up": "",
            "outside": True,
        })

    # take top matches and build answer from best block layers + extra snippets
    top = gathered[:4]
    primary = top[0][1]
    layer = _extract_layer(primary, depth)
    answer = _clean_speak(layer)
    # if still thin, pull another high-scoring snippet
    if len(answer.split()) < 25 and len(top) > 1:
        extra = _clean_speak(_extract_layer(top[1][1], 0))
        if extra and extra not in answer:
            answer = (answer + " " + extra).strip()
    if len(answer.split()) > 100:
        answer = " ".join(answer.split()[:100]) + "."

    # strip any leftover meta / reference labels
    for bad in (
        "according to", "matthew henry", "cross reference", "cross references",
        "angel is designed", "i am designed", "my instructions", "as an ai",
        "biblical doctrine", "classic teaching", "probe instruction",
    ):
        if bad in answer.lower():
            # remove sentences containing meta
            sents = re.split(r"(?<=[.!?])\s+", answer)
            answer = " ".join(s for s in sents if bad not in s.lower()).strip()

    _LAST_TOPIC[uid] = {
        "topic": topic_q,
        "query": q,
        "depth": depth,
        "full_body": primary,
        "ref": "",
        "block_key": None,
    }
    return JSONResponse({
        "ok": True,
        "answer": answer or "",
        "follow_up": "",
        "outside": not bool(answer),
        "topic": topic_q,
        "depth": depth,
    })


@router.get("/member/hymns", response_class=HTMLResponse)
async def hymns_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("kwealth/hymns.html", {"request": request, "user": user})


def _parse_hymn_text(text: str, start_num: int = 1) -> list:
    hymns = []
    if not text:
        return hymns
    for m in re.finditer(r"\{(\d+)\}\s*([^\n]+)\n(.*?)(?=\n\{\d+\}|\n={3,}|\nB\. TITLE|\Z)", text, re.S):
        num, title, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        hymns.append({
            "number": int(num),
            "title": title.title() if title.isupper() else title,
            "body": body,
            "source": "pack",
        })
    # fallback: numbered lines "1. TITLE" only if nothing parsed
    if not hymns:
        chunks = re.split(r"\n(?=\d+\.\s+[A-Z])", text)
        n = start_num
        for c in chunks:
            c = c.strip()
            if not c:
                continue
            first, _, rest = c.partition("\n")
            hymns.append({"number": n, "title": first[:120], "body": rest or first, "source": "pack"})
            n += 1
    return hymns


@router.get("/member/api/hymns")
async def hymns_api(user: User = Depends(require_user), session: Session = Depends(get_session)):
    hymns = []
    path = _angel_resource_path("hymns_public_domain.txt")
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for h in _parse_hymn_text(text):
            h["source"] = "public domain"
            hymns.append(h)
    # global church pack + platform default
    try:
        from app.models import ChurchHymnal, ChurchMember, ChurchUnit
        cm = session.exec(select(ChurchMember).where(ChurchMember.user_id == user.id)).first()
        gid = getattr(cm, "global_church_id", None) if cm else None
        packs = []
        if gid:
            packs = session.exec(
                select(ChurchHymnal).where(
                    ChurchHymnal.is_active == True,
                    ChurchHymnal.church_id == gid,
                )
            ).all()
        packs += session.exec(
            select(ChurchHymnal).where(
                ChurchHymnal.is_active == True,
                ChurchHymnal.church_id == None,
            )
        ).all()
        base = max([h["number"] for h in hymns], default=0)
        for pack in packs:
            extra = _parse_hymn_text(pack.body or "", start_num=base + 1)
            for h in extra:
                h["source"] = pack.title or "Church hymnal"
                h["number"] = base + 1
                base += 1
                hymns.append(h)
    except Exception:
        pass
    return JSONResponse({"hymns": hymns, "count": len(hymns)})
