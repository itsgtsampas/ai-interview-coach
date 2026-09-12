# Optional Unicode font

The scorecard PDF renders with fpdf2's built-in Helvetica, whose encoding is
Latin-1. That covers English and the typographic punctuation this application
produces (see `_SANITISE` in `app/services/pdf_export.py`), but not Greek,
Cyrillic or CJK — those characters are replaced with `?`.

To render the full Unicode range, drop a TrueType font here:

    app/assets/fonts/DejaVuSans.ttf
    app/assets/fonts/DejaVuSans-Bold.ttf

`pdf_export.py` detects them on startup and registers them automatically; no
code change is needed. They are not committed because a ~1.5 MB binary in a
teaching repository has to earn its place, and the English path does not need it.
