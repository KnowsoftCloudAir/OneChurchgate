# Kwealth Reading Room — split Settings / Full-screen architecture

## What changed
1. `/member/kwealth/reading/settings?book_id=ID` is the **settings-only** page. The book is retained in the DOM only as a data source for speech; it is not visually displayed.
2. Clicking **Read / Voice** starts browser speech synthesis from the selected book.
3. Clicking **Full-screen Reading** opens the dedicated presentation page.
4. `/member/kwealth/reading/fullscreen?book_id=ID` is the **3D presentation** page.
5. Full-screen presentation shows the title at the top centre and sentence-by-sentence captions while speech runs.
6. Left/right changes pages. Up/down changes the selected animation.
7. `sceneMix=one` selects a specific animation; `sceneMix=mix` enables the existing mix behavior.

## Router integration
Copy `templates/reading_room_settings.html` and `templates/reading_room_fullscreen.html` into your Flask templates directory.
Copy `routes_reading_room.py` into the application and register its blueprint.

The only application-specific work is implementing `get_member_books_and_book(book_id)` by reusing the existing data-loading portion of your current `/member/kwealth/books` route. This avoids guessing your database/model names.

## Important
The templates preserve the original Reading Room's CSS/3D scene assets and JavaScript behavior. They are designed as a split UI rather than a replacement for your existing book storage or authentication logic.
