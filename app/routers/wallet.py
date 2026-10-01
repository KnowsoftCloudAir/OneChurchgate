
"""Member Wallet — income, expenses, charts, balance badge."""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List
from collections import defaultdict

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, Field, SQLModel, Column
from sqlalchemy import Column as SAColumn, Float

from app.database import get_session, engine
from app.auth import require_user
from app.models import User

router = APIRouter(tags=["wallet"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


class WalletEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    kind: str = Field(max_length=20, index=True)  # income | expense
    amount: float = Field(default=0.0)
    currency: str = Field(default="NGN", max_length=8)
    payment_method: Optional[str] = Field(default=None, max_length=20)
    source: Optional[str] = Field(default=None, max_length=80)
    category: Optional[str] = Field(default=None, max_length=80)
    note: Optional[str] = Field(default=None, max_length=500)
    entry_date: date = Field(default_factory=date.today, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


def _ensure_table():
    try:
        SQLModel.metadata.create_all(engine, tables=[WalletEntry.__table__])
    except Exception as e:
        print("wallet table:", e)


def _summary(session: Session, user_id: int):
    rows = list(session.exec(select(WalletEntry).where(WalletEntry.user_id == user_id)).all())
    income = sum(r.amount for r in rows if r.kind == "income")
    expense = sum(r.amount for r in rows if r.kind == "expense")
    balance = income - expense
    pct = (balance / income * 100.0) if income > 0 else 0.0
    healthy = pct >= 20.0 if income > 0 else balance >= 0
    # monthly
    by_month_in = defaultdict(float)
    by_month_ex = defaultdict(float)
    by_src = defaultdict(float)
    by_cat = defaultdict(float)
    for r in rows:
        key = r.entry_date.strftime("%Y-%m") if r.entry_date else "unknown"
        if r.kind == "income":
            by_month_in[key] += r.amount
            by_src[(r.source or "Other")] += r.amount
        else:
            by_month_ex[key] += r.amount
            by_cat[(r.category or "Other")] += r.amount
    return {
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(balance, 2),
        "pct": round(pct, 1),
        "healthy": healthy,
        "rows": rows,
        "by_month_in": dict(sorted(by_month_in.items())),
        "by_month_ex": dict(sorted(by_month_ex.items())),
        "by_src": dict(sorted(by_src.items(), key=lambda x: -x[1])[:12]),
        "by_cat": dict(sorted(by_cat.items(), key=lambda x: -x[1])[:12]),
    }


@router.get("/member/wallet", response_class=HTMLResponse)
async def wallet_page(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    _ensure_table()
    s = _summary(session, user.id)
    return templates.TemplateResponse(
        "wallet/index.html",
        {"request": request, "user": user, "s": s, "ok": request.query_params.get("ok")},
    )


@router.get("/member/wallet/summary.json")
async def wallet_summary_json(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    _ensure_table()
    s = _summary(session, user.id)
    return JSONResponse({
        "income": s["income"],
        "expense": s["expense"],
        "balance": s["balance"],
        "pct": s["pct"],
        "healthy": s["healthy"],
    })


@router.post("/member/wallet/add")
async def wallet_add(
    kind: str = Form(...),
    amount: float = Form(...),
    payment_method: str = Form(""),
    source: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    entry_date: str = Form(""),
    custom_source: str = Form(""),
    custom_category: str = Form(""),
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    _ensure_table()
    kind = (kind or "").strip().lower()
    if kind not in ("income", "expense"):
        return RedirectResponse("/member/wallet?ok=bad", status_code=303)
    try:
        amt = float(amount)
    except Exception:
        return RedirectResponse("/member/wallet?ok=bad", status_code=303)
    if amt <= 0:
        return RedirectResponse("/member/wallet?ok=bad", status_code=303)
    d = date.today()
    if entry_date:
        try:
            d = date.fromisoformat(entry_date)
        except Exception:
            pass
    src = (custom_source or source or "").strip()[:80] or None
    cat = (custom_category or category or "").strip()[:80] or None
    row = WalletEntry(
        user_id=user.id,
        kind=kind,
        amount=amt,
        payment_method=(payment_method or None) if kind == "income" else None,
        source=src if kind == "income" else None,
        category=cat if kind == "expense" else None,
        note=(note or "").strip()[:500] or None,
        entry_date=d,
    )
    session.add(row)
    session.commit()
    return RedirectResponse("/member/wallet?ok=1", status_code=303)


@router.post("/member/wallet/{entry_id}/delete")
async def wallet_delete(
    entry_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
):
    _ensure_table()
    row = session.get(WalletEntry, entry_id)
    if row and row.user_id == user.id:
        session.delete(row)
        session.commit()
    return RedirectResponse("/member/wallet?ok=deleted", status_code=303)
