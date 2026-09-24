# Kwealth Books — Full Working Upgrade (v3)

## Important
Previous packages failed because upgrade JS ran **before** core functions existed.
**v3 hard-wires the fix at the end of the script** and forces CSS so the book sheet is fully hidden when Scene is on.

## Install (replace these 3 files in your repo)

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

cp /path/to/kwealth_v3/templates/kwealth/books.html templates/kwealth/
cp /path/to/kwealth_v3/templates/admin/library.html templates/admin/
cp /path/to/kwealth_v3/app/routers/admin.py app/routers/

git add templates/kwealth/books.html templates/admin/library.html app/routers/admin.py
git commit -m "Kwealth v3: scene replaces book, text on scene, swipe, admin multi-upload"
git push
```

Redeploy, then **hard-refresh** the browser (Ctrl+Shift+R or Cmd+Shift+R).

## Verify
1. Open a book → tap **Scene** → paper book disappears; only animation shows.
2. Tap **Read** → words appear on the scene.
3. Console shows: `[Kwealth] v3 ready — scene replaces book, overlay text, swipe`
4. Swipe left/right = pages; up/down = change scenes.
5. Admin → Library → multi-select PDFs → Upload books.

## Features
- Scene fully replaces book (no dual screens)
- Words display on 3D/CSS scene while voice reads
- Better fonts (Playfair, Cinzel, Inter) + entrance styles
- Finger swipe pages + scenes
- Admin multi-book upload
- Member book/BGM upload already supported by existing routes
