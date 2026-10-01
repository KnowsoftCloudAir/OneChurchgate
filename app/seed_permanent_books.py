"""Seed permanent books into static/books + KwealthBook rows."""
from __future__ import annotations
from pathlib import Path
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parent.parent
STATIC_BOOKS = ROOT / "static" / "books"
STATIC_BOOKS.mkdir(parents=True, exist_ok=True)

PERMANENT = [
    ("The Power of Positive Thinking", "Norman Vincent Peale", "power_of_positive_thinking.txt"),
    ("You Can Win", "Shiv Khera", "you_can_win.txt"),
    ("Piercing the Darkness", "Frank E. Peretti", "piercing_the_darkness.txt"),
]

def seed_permanent_library(session: Session, force: bool = False) -> dict:
    from app.models import KwealthBook
    added = 0
    for title, author, fname in PERMANENT:
        src = STATIC_BOOKS / fname
        # also try data path
        if not src.exists():
            alt = ROOT / "data" / "kwealth_books" / fname
            if alt.exists():
                src.write_bytes(alt.read_bytes())
        if not src.exists():
            print("missing book file", fname)
            continue
        # relative path as used by kwealth loader
        rel = f"books/{fname}"
        existing = session.exec(select(KwealthBook).where(KwealthBook.title == title)).first()
        if existing and not force:
            continue
        if existing and force:
            existing.author = author
            existing.source_path = rel
            existing.is_active = True
            existing.owner_user_id = None
            session.add(existing)
        else:
            session.add(KwealthBook(
                title=title,
                author=author,
                source_path=rel,
                page_count=1,
                is_active=True,
                is_premium=False,
                owner_user_id=None,
            ))
        added += 1
    session.commit()
    return {"ok": True, "books": added, "bgm": 0}
