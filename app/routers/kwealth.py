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
    ):
        clean = re.sub(re.escape(prefix), "", clean, flags=re.I)
    # remove bullet markers for smoother speech
    clean = re.sub(r"[•\-]\s*", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
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


@router.post("/member/api/angel-ask")
async def angel_ask(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Conversational Angel: match study layers, continue on more, rarely refuse."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    q = (data.get("question") or data.get("q") or "").strip()
    topic_hint = (data.get("topic") or "").strip()
    if not q:
        return JSONResponse({"ok": True, "answer": "How may I help you?", "follow_up": "What would you like to learn from the Word?", "outside": False})

    ql = q.lower().strip()
    uid = user.id
    resource = _load_topic_resource(session)
    last = _LAST_TOPIC.get(uid) or {}

    is_more = (
        ql in ("more", "tell me more", "more please", "continue", "go on", "yes", "yeah", "yep", "sure", "ok", "okay", "please")
        or ql.startswith("more ")
        or "tell me more" in ql
        or "go deeper" in ql
        or "explain more" in ql
    )

    # Resolve topic question
    topic_q = q
    depth = 0
    if is_more:
        topic_q = last.get("topic") or topic_hint or last.get("query") or "faith jesus salvation"
        depth = int(last.get("depth") or 0) + 1
    else:
        # if short reply while we had a topic, treat as continue
        if last.get("topic") and len(ql.split()) <= 4 and not any(
            k in ql for k in ("play", "music", "stop", "manna", "off", "status")
        ):
            # could be a new short topic or continue — prefer match first
            pass

    # Excerpts first
    excerpts = session.exec(
        select(KwealthExcerpt).where(KwealthExcerpt.user_id == user.id).order_by(KwealthExcerpt.created_at.desc()).limit(40)
    ).all()
    words = [w for w in re.findall(r"[a-z']{3,}", topic_q.lower()) if len(w) > 2]
    matched = []
    for e in excerpts:
        blob = f"{e.title or ''} {e.body or ''} {e.source or ''}".lower()
        score = sum(1 for w in words if w in blob)
        if score:
            matched.append((score, e))
    matched.sort(key=lambda x: -x[0])

    ref_name = None
    body = None
    block_key = None

    if matched and not is_more:
        e = matched[0][1]
        ref_name = (e.source or e.title or "your saved excerpts").strip()
        body = (e.body or "").strip()
        block_key = "excerpt"
    else:
        ref_name, body, block_key = _find_topic_block(resource, topic_q)
        if not body and topic_hint:
            ref_name, body, block_key = _find_topic_block(resource, topic_hint)

    # If more and same block stored, use stored full body for layering
    if is_more and last.get("full_body"):
        body = last.get("full_body") or body
        ref_name = last.get("ref") or ref_name
        block_key = last.get("block_key") or block_key

    if not body:
        # broad fallbacks so we rarely say sorry
        topical = {
            "faith": "Faith is confidence in God and His word. It comes by hearing the word of Christ. Without faith it is impossible to please God. Hebrews 11:1, Romans 10:17, Hebrews 11:6.",
            "prayer": "Prayer is talking with God in faith. Ask, seek, and knock. Be anxious for nothing; in everything by prayer and thanksgiving make your requests known to God. Matthew 7:7, Philippians 4:6, 1 Thessalonians 5:17.",
            "jesus": "Jesus is the Son of God, the Saviour. Whoever believes in Him shall not perish but have everlasting life. He is the way, the truth, and the life. John 3:16, John 14:6, Acts 4:12.",
            "god": "God is the living Creator of heaven and earth, holy and loving. There is one God — Father, Son, and Holy Spirit. Genesis 1:1, Deuteronomy 6:4, Matthew 28:19.",
            "heaven": "Heaven is God's dwelling place. Jesus prepares a place for His people. One day God will wipe away every tear; there will be no death, sorrow, or pain. John 14:2-3, Revelation 21:4, Revelation 22:4.",
            "hell": "Scripture warns of eternal punishment for the unrepentant, and the lake of fire as the second death. The way of escape is Jesus Christ today. Matthew 25:41, Revelation 20:15, John 3:16-18.",
            "rapture": "The Lord will descend with a shout and the trumpet of God. The dead in Christ rise first; then living believers are caught up to meet the Lord in the air. 1 Thessalonians 4:16-17, 1 Corinthians 15:51-52, John 14:3.",
            "bible": "All scripture is given by inspiration of God and is profitable for doctrine, reproof, correction, and instruction in righteousness. 2 Timothy 3:16-17, Psalm 119:105, 2 Peter 1:21.",
            "love": "Love the Lord your God with all your heart. Love one another as Christ loved us. 1 John 4:7-8, John 13:34, Deuteronomy 6:5.",
            "peace": "Jesus said, Peace I leave with you. His peace guards the heart when we trust Him. John 14:27, Philippians 4:7, Isaiah 26:3.",
        }
        for key, text_fb in topical.items():
            if key in topic_q.lower() or key in ql:
                ref_name, body = "the Bible", text_fb
                break

    if not body and last.get("full_body"):
        body = last["full_body"]
        ref_name = last.get("ref") or "the Bible"
        depth = int(last.get("depth") or 0) + 1
        is_more = True
        topic_q = last.get("topic") or topic_q

    if not body:
        # soft recovery instead of hard sorry
        return JSONResponse({
            "ok": True,
            "answer": "Let us open the Word together. You can ask about God, Jesus, heaven, prayer, repentance, holiness, the rapture, or any of the Bible doctrines. What would you like to hear?",
            "follow_up": "Would you like me to start with who Jesus is?",
            "outside": False,
        })

    full_body = body
    layer_text = _extract_layer(full_body, depth)
    answer = _clean_speak(layer_text)

    # encouragement tail on deeper layers
    if depth >= 1 and "trust" not in answer.lower() and len(answer.split()) < 80:
        answer = answer.rstrip(".") + ". Love God, walk with Him daily, and trust Him with your life."

    _LAST_TOPIC[uid] = {
        "topic": topic_q if not is_more else (last.get("topic") or topic_q),
        "query": q,
        "depth": depth,
        "full_body": full_body,
        "ref": ref_name or "",
        "block_key": block_key,
        "offset": depth,
    }

    follow = _make_follow_up(topic_q, full_body, resource, depth)
    return JSONResponse({
        "ok": True,
        "answer": answer,
        "follow_up": follow,
        "outside": False,
        "topic": _LAST_TOPIC[uid]["topic"],
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
