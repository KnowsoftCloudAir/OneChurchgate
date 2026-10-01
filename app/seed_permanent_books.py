"""Seed permanent Kwealth books + nature BGM (like stream library).
Call once from main lifespan or admin button.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "data" / "kwealth_books"
BGM_DIR = ROOT / "data" / "kwealth_bgm"

PERMANENT_BOOKS = [
    {
        "title": "The Power of Positive Thinking",
        "author": "Norman Vincent Peale",
        "filename": "The_Power_of_Positive_Thinking_Norman_Vincent_Peale.txt",
        "category": "inspiration",
        "description": "Classic guide to faith, confidence, and victorious living.",
    },
    {
        "title": "You Can Win",
        "author": "Shiv Khera",
        "filename": "You_Can_Win_Shiv_Khera.txt",
        "category": "inspiration",
        "description": "Winners don't do different things — they do things differently.",
    },
    {
        "title": "Piercing the Darkness",
        "author": "Frank E. Peretti",
        "filename": "Piercing_the_Darkness_Frank_Peretti.txt",
        "category": "fiction",
        "description": "Spiritual warfare novel — sequel to This Present Darkness.",
    },
]

def seed_permanent_library(session: Session, force: bool = False) -> dict:
    """Insert books into KwealthBook (or equivalent) if model exists."""
    added_books = 0
    added_bgm = 0
    try:
        from app.models import KwealthBook  # adjust if named differently
    except Exception:
        try:
            from app.models import LibraryBook as KwealthBook
        except Exception as e:
            print("No KwealthBook model:", e)
            return {"ok": False, "error": "model_missing", "books": 0, "bgm": 0}

    for meta in PERMANENT_BOOKS:
        path = BOOKS_DIR / meta["filename"]
        if not path.exists():
            print("missing", path)
            continue
        existing = session.exec(
            select(KwealthBook).where(KwealthBook.title == meta["title"])
        ).first()
        if existing and not force:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        kwargs = dict(
            title=meta["title"],
            author=meta.get("author") or "",
            content=text,
            is_active=True,
            is_public=True,
        )
        # optional fields
        for k, v in [
            ("category", meta.get("category")),
            ("description", meta.get("description")),
            ("source_filename", meta["filename"]),
            ("permanent", True),
        ]:
            if hasattr(KwealthBook, k.split("=")[0] if False else k):
                kwargs[k] = v
        try:
            if existing and force:
                for k, v in kwargs.items():
                    if k != "title":
                        setattr(existing, k, v)
                session.add(existing)
            else:
                session.add(KwealthBook(**{k: v for k, v in kwargs.items() if True}))
            added_books += 1
        except Exception as e:
            print("book seed error", meta["title"], e)

    # BGM
    try:
        from app.models import KwealthBgm
        bgm_path = BGM_DIR / "nature_ambient.mp3"
        if bgm_path.exists():
            ex = session.exec(select(KwealthBgm).where(KwealthBgm.title == "Nature Ambient")).first()
            if not ex or force:
                # store relative URL path for static serve
                rel = "/static/kwealth_bgm/nature_ambient.mp3"
                # also copy to static if needed by caller
                if not ex:
                    session.add(KwealthBgm(title="Nature Ambient", file_url=rel, is_active=True))
                    added_bgm = 1
    except Exception as e:
        print("bgm seed:", e)

    session.commit()
    return {"ok": True, "books": added_books, "bgm": added_bgm}
