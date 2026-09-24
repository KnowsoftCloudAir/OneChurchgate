# Kwealth FINAL fix — words on 3D scene

## Why earlier packages failed

The app was writing the spoken words **inside the book panel** (`#sheetText` inside `.page-sheet`).

When Scene was turned on and the book panel was hidden, **the words were hidden with it**.

## What this package actually changes

In `templates/kwealth/books.html`:

1. **When Scene is ON** → book panel (`.page-sheet`) is fully hidden.
2. **Spoken words** are written to `#overlayText` inside `#sceneTextOverlay`, which sits **on top of the 3D scene** (sibling of the book panel, not inside it).
3. As the voice reads, `highlightWord` / `showSentence` update the overlay so words appear on the animation.

Also includes:
- `templates/admin/library.html` — multi-file book upload form
- `app/routers/admin.py` — `POST /admin/library/books` multi-upload route

## Install

Replace these files in your OneChurchgate repo:

```
templates/kwealth/books.html
templates/admin/library.html
app/routers/admin.py
```

```bash
cd OneChurchgate
cp templates/kwealth/books.html templates/kwealth/books.html.bak
cp templates/admin/library.html templates/admin/library.html.bak
cp app/routers/admin.py app/routers/admin.py.bak

cp /path/to/kwealth_FINAL/templates/kwealth/books.html templates/kwealth/
cp /path/to/kwealth_FINAL/templates/admin/library.html templates/admin/
cp /path/to/kwealth_FINAL/app/routers/admin.py app/routers/

git add templates/kwealth/books.html templates/admin/library.html app/routers/admin.py
git commit -m "Fix: spoken words on 3D scene overlay; hide book panel when Scene on; admin multi-upload"
git push
```

Redeploy, then hard-refresh the browser (Ctrl+Shift+R).

## How to test (must work)

1. Open any book in Kwealth → Books.
2. Tap **Scene** — paper book must disappear; only the animation remains.
3. Tap **Read** — sentences/words must appear **on the animation**, not on a book page.
4. Words should highlight as the voice reads.
5. Admin → Library → choose several PDF/TXT files → **Upload books**.

## If Scene still shows the book

- Confirm deploy used the new `books.html`.
- Hard refresh / clear cache.
- In DevTools: `#stage` should have class `scene-on`; `.page-sheet` should be `display: none`; `#sceneTextOverlay` should be visible with text inside `#overlayText`.
