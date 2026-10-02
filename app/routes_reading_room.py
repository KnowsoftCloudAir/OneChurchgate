from flask import Blueprint, render_template, request, redirect, url_for

# Dedicated Reading Room routes.
# IMPORTANT: replace get_member_books_and_book() below with the same helper/query
# your existing /member/kwealth/books route already uses.
reading_room_bp = Blueprint("reading_room", __name__)

def get_member_books_and_book(book_id):
    """Return (books, book, pages, page_index, my_books).

    Reuse the data-loading code from your existing Kwealth books route so that
    permissions, shared books and page extraction remain exactly the same.
    """
    raise NotImplementedError("Wire this to your existing Kwealth book loader")

@reading_room_bp.get("/member/kwealth/reading/settings")
def reading_room_settings():
    book_id = request.args.get("book_id", type=int)
    books, book, pages, page_index, my_books = get_member_books_and_book(book_id)
    return render_template(
        "reading_room_settings.html",
        books=books, book=book, pages=pages, page_index=page_index, my_books=my_books
    )

@reading_room_bp.get("/member/kwealth/reading/fullscreen")
def reading_room_fullscreen():
    book_id = request.args.get("book_id", type=int)
    books, book, pages, page_index, my_books = get_member_books_and_book(book_id)
    if not book:
        return redirect(url_for("reading_room.reading_room_settings"))
    return render_template(
        "reading_room_fullscreen.html",
        books=books, book=book, pages=pages, page_index=page_index, my_books=my_books
    )

# Register in the main Flask app with:
# from routes_reading_room import reading_room_bp
# app.register_blueprint(reading_room_bp)
