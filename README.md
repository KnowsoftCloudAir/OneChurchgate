# Kwealth Books Full Upgrade (v2 — fixed)

Drop-in package for https://github.com/KnowsoftCloudAir/OneChurchgate

## Why v1 had no effect

The first upgrade script ran **before** `applyScene` / `renderPage` were defined, so the patches never attached.  
This v2 package:

1. Removes the broken early upgrade block  
2. Installs **Fix v2 at the end of the script** (after all functions exist)  
3. Forces CSS so the book sheet is fully hidden when Scene is on  
4. Renders reading text onto `#sceneTextOverlay` on top of the 3D scene  

## What you get

| Feature | Behaviour |
|--------|-----------|
| Scene on | Book sheet **hidden**; only 3D/CSS scene visible |
| Words on scene | Text overlay on the scene while voice reads |
| Fullscreen | Scene fills the viewport; text stays on top |
| Swipe ← → | Next / previous page |
| Swipe ↑ ↓ | Next / previous 3D scene (when Scene or Fullscreen is on) |
| Fonts | Georgia, Playfair, Cinzel, Inter, etc. |
| Word styles | fill, fade-up, typewriter, scale-in, glow, center-block |
| Admin multi-upload | `POST /admin/library/books` — multiple PDF/TXT/DOCX |
| Member upload | Already supported by existing kwealth routes |

## Files to copy (replace existing)

```
templates/kwealth/books.html    ← main reader fix
templates/admin/library.html    ← multi-book admin UI
app/routers/admin.py            ← multi-book upload route
```

`app/routers/kwealth.py` is included for reference only (member uploads already work).

## Apply

```bash
git clone https://github.com/KnowsoftCloudAir/OneChurchgate.git
cd OneChurchgate

cp templates/kwealth/books.html templates/kwealth/books.html.bak
cp templates/admin/library.html templates/admin/library.html.bak
cp app/routers/admin.py app/routers/admin.py.bak

# From this unzipped folder:
cp templates/kwealth/books.html  /path/to/OneChurchgate/templates/kwealth/
cp templates/admin/library.html  /path/to/OneChurchgate/templates/admin/
cp app/routers/admin.py          /path/to/OneChurchgate/app/routers/

git add templates/kwealth/books.html templates/admin/library.html app/routers/admin.py
git commit -m "Kwealth v2: scene replaces book, text overlay, swipe, admin multi-upload"
git push
```

Redeploy (e.g. Render) after push. Hard-refresh the browser (Ctrl+Shift+R).

## Verify

1. Open any book in **Kwealth → Books**.  
2. Tap **Scene** — the paper book must disappear; only the animation remains.  
3. Start **Read** — words appear centered on the scene.  
4. Enter **Fullscreen** — same behaviour, full screen.  
5. Swipe left/right for pages; up/down to change scenes.  
6. Browser console should log: `[Kwealth] Fix v2 active: scene-replaces-book, overlay text, swipe`  
7. Admin → Library → select several PDFs → **Upload books**.

## Debug

If Scene still shows the book sheet:

- Hard refresh / clear cache  
- Confirm deploy picked up the new `books.html`  
- In DevTools, inspect `#stage` — it must have class `scene-on`  
- Inspect `#sheet` (page-sheet) — computed style should be `display: none`  
- Console must show the Fix v2 log line  
