"""SMTP mailer for Churchgate (knowsoft.org.uk).

Env:
  MAIL_HOST, MAIL_PORT, MAIL_USER, MAIL_PASSWORD, MAIL_FROM
  MAIL_FROM_NAME  (default: Churchgate)
  PUBLIC_BASE_URL (default: https://knowsoft.org.uk)
  MAIL_DISABLED=1  → log only (no send)
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from typing import Optional, Tuple


def public_base() -> str:
    """Public URL of this app. knowsoft.org.uk does not serve Churchgate routes."""
    raw = (os.getenv("PUBLIC_BASE_URL") or "https://onechurchgate1.onrender.com").rstrip("/")
    if "knowsoft.org.uk" in raw:
        return "https://onechurchgate1.onrender.com"
    return raw


def from_addr() -> Tuple[str, str]:
    name = os.getenv("MAIL_FROM_NAME") or "Churchgate"
    addr = os.getenv("MAIL_FROM") or os.getenv("MAIL_USER") or "noreply@knowsoft.org.uk"
    return name, addr


def send_mail(to_email: str, subject: str, text_body: str, html_body: Optional[str] = None) -> bool:
    to_email = (to_email or "").strip()
    if not to_email:
        return False
    name, addr = from_addr()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{name} <{addr}>"
    msg["To"] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if os.getenv("MAIL_DISABLED", "").strip() in ("1", "true", "yes"):
        print(f"[mail:disabled] to={to_email} subject={subject}")
        return True

    host = os.getenv("MAIL_HOST") or os.getenv("SMTP_HOST")
    user = os.getenv("MAIL_USER") or os.getenv("SMTP_USER")
    password = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD") or os.getenv("MAIL_PASS")
    port = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT") or "587")
    if not host or not user or not password:
        print("⚠️ Mail not configured: set MAIL_HOST, MAIL_USER, MAIL_PASSWORD")
        return False
    try:
        with smtplib.SMTP(host, port, timeout=25) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except Exception:
                pass
            smtp.login(user, password)
            smtp.send_message(msg)
        print(f"✅ Mail sent {to_email} @ {datetime.utcnow().isoformat()}Z")
        return True
    except Exception as e:
        print(f"❌ Mail fail {to_email}: {e}")
        return False


def branded(title: str, body_html: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Georgia,serif;background:#0f172a;color:#e2e8f0;padding:24px">
  <div style="max-width:560px;margin:auto;background:#111827;border:1px solid #334155;border-radius:16px;padding:24px">
    <div style="font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#94a3b8">Churchgate · Knowsoft</div>
    <h1 style="font-size:22px;color:#f8fafc">{title}</h1>
    <div style="line-height:1.6;color:#cbd5e1">{body_html}</div>
    <p style="margin-top:28px;font-size:12px;color:#64748b">{public_base()}</p>
  </div></body></html>"""
