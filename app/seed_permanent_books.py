
"""Load permanent books + nature BGM into the same paths admin upload uses."""
from __future__ import annotations
from pathlib import Path
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parent.parent  # app/
STATIC = ROOT / "static"
TEXT_DIR = STATIC / "uploads" / "kwealth_books_text"
BGM_DIR = STATIC / "uploads" / "kwealth_bgm" / "admin_global"
TEXT_DIR.mkdir(parents=True, exist_ok=True)
BGM_DIR.mkdir(parents=True, exist_ok=True)

BOOKS = [
    ("The Power of Positive Thinking", "Norman Vincent Peale", "permanent_the_power_of_positive_thinking.txt"),
    ("You Can Win", "Shiv Khera", "permanent_you_can_win.txt"),
    ("Piercing the Darkness", "Frank E. Peretti", "permanent_piercing_the_darkness.txt"),
]

def seed_permanent_library(session: Session, force: bool = False) -> dict:
    from app.models import KwealthBook
    added = 0
    for title, author, fname in BOOKS:
        path = TEXT_DIR / fname
        if not path.exists():
            print("missing", path)
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        pages = max(1, len(text) // 1800 + 1)
        existing = session.exec(select(KwealthBook).where(KwealthBook.title == title)).first()
        # source_path: absolute path string as admin upload does, or relative
        sp = str(path)
        if existing:
            if force:
                existing.author = author
                existing.source_path = sp
                existing.page_count = pages
                existing.is_active = True
                existing.is_premium = False
                existing.owner_user_id = None
                session.add(existing)
                added += 1
            continue
        session.add(KwealthBook(
            title=title,
            author=author,
            source_path=sp,
            page_count=pages,
            is_active=True,
            is_premium=False,
            owner_user_id=None,
        ))
        added += 1
    session.commit()
    return {"ok": True, "books": added, "bgm": 1 if (BGM_DIR / "nature_ambient.mp3").exists() else 0}
