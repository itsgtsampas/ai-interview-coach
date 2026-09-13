# Bundled Unicode font

`DejaVuSans*.ttf` — used by the scorecard PDF export (`app/services/pdf_export.py`).

fpdf2's built-in Helvetica is Latin-1, so without a TrueType face a Greek
scorecard renders as `?`. These are registered automatically when present; if
they are removed the export falls back to Helvetica and transliterates, which
still works for English.

DejaVu Sans 2.37, from the project's own release:
<https://github.com/dejavu-fonts/dejavu-fonts>

Licence in `LICENSE.dejavu.txt`. Bitstream Vera plus Arev — both permit
redistribution and modification without fee, which is why this face and not a
system font: macOS and Microsoft faces cannot be committed to a repository.
