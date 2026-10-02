# Reading Room Permanent Fix — Settings Always Available

Package for: https://github.com/KnowsoftCloudAir/OneChurchgate

## What this fixes

In the dedicated **Reading Room** (`/member/kwealth/books/reading-room?book_id=...`) the full reading settings panel was starting closed / hard to discover (“hiding between Book Library and Reading Room”).

After this fix the following controls are **visible by default** as soon as a book is open in the Reading Room:

1. Reading themes (Parchment, Night, Sepia, Forest, Ocean)
2. Font & font size
3. Page-flip styles
4. Page navigation / jump
5. Voice / read-aloud
6. Reading speed (rate)
7. Paragraph pauses
8. Background music (Music chip)
9. 3D scenes / ambience (Scene + picker, including Knowsoft wall clock)
10. Full-screen reading
11. Knowsoft clock scene option

The ⚙ button still toggles the panel open/closed. Outside click and Escape still close it.

## Files in this package

```
app/templates/kwealth/reading_room.html   ← FIXED template (drop-in replacement)
apply_reading_room_fix.py                 ← original route helper (already applied in many deploys)
apply_reading_room_permanent_fix.py       ← dual-route helper (optional)
apply_reading_room_settings_fix.py        ← older settings init patch (superseded by the template)
READING_ROOM_FIX.md
BOOK_LIBRARY_UPDATE.md
README_APPLY.md                           ← this file
```

## How to apply (recommended)

From the root of your OneChurchgate clone:

```bash
# 1. Backup current file
cp app/templates/kwealth/reading_room.html app/templates/kwealth/reading_room.html.bak

# 2. Copy the fixed template
cp /path/to/this/package/app/templates/kwealth/reading_room.html \
   app/templates/kwealth/reading_room.html

# 3. Confirm the route exists (should already be present)
grep -n "reading-room" app/routers/kwealth.py

# 4. Restart the app (Render / uvicorn / etc.)
```

If the route is missing, also run:

```bash
python apply_reading_room_fix.py
# or
python apply_reading_room_permanent_fix.py
```

## Acceptance checks

1. Open Book Library → click any book cover → lands on  
   `/member/kwealth/books/reading-room?book_id=...`
2. **Reading settings panel is open** under the ⚙ button (themes, fonts, flip, jump, voice, rate, paragraph pause).
3. ⚙ still toggles the panel closed/open.
4. Music / Scene / Full screen chips work as before.
5. “← Library” and “← Kwealth” navigation links are present.
6. Knowsoft clock appears in the scene picker.

## Notes

- App loads templates from `app/templates/` (see `main.py`).
- Library page (`books.html`) stays a clean shelf; only the Reading Room shows the full reader + settings.
- Personal upload limits and format rules are unchanged.
