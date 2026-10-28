"""Print-ready PDF interiors for Amazon KDP paperbacks (a Candle Premium feature).

Sizes and margins follow KDP's "Set Trim Size, Bleed, and Margins" help page.
Interiors are made without bleed: a novel's text never runs to the page edge.
The layout itself is resources/kdp.typ, set by Typst.
"""

import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import export

TEMPLATE = Path(__file__).parent / "resources" / "kdp.typ"
MIN_PAGES = 24

# label -> (width in, height in, max pages on white paper, on cream paper)
TRIM_SIZES = {
    "5 × 8 in (12.7 × 20.32 cm)": (5, 8, 828, 776),
    "5.06 × 7.81 in (12.85 × 19.84 cm)": (5.06, 7.81, 828, 776),
    "5.25 × 8 in (13.34 × 20.32 cm)": (5.25, 8, 828, 776),
    "5.5 × 8.5 in (13.97 × 21.59 cm)": (5.5, 8.5, 828, 776),
    "6 × 9 in (15.24 × 22.86 cm)": (6, 9, 828, 776),
    "6.14 × 9.21 in (15.6 × 23.39 cm)": (6.14, 9.21, 828, 776),
    "6.69 × 9.61 in (16.99 × 24.41 cm)": (6.69, 9.61, 828, 776),
    "7 × 10 in (17.78 × 25.4 cm)": (7, 10, 828, 776),
    "7.44 × 9.69 in (18.9 × 24.61 cm)": (7.44, 9.69, 828, 776),
    "7.5 × 9.25 in (19.05 × 23.5 cm)": (7.5, 9.25, 828, 776),
    "8 × 10 in (20.32 × 25.4 cm)": (8, 10, 828, 776),
    "8.25 × 6 in (20.96 × 15.24 cm)": (8.25, 6, 800, 750),
    "8.25 × 8.25 in (20.96 × 20.96 cm)": (8.25, 8.25, 800, 750),
    "8.5 × 8.5 in (21.59 × 21.59 cm)": (8.5, 8.5, 590, 550),
    "8.5 × 11 in (21.59 × 27.94 cm)": (8.5, 11, 590, 550),
    "8.27 × 11.69 in (21 × 29.7 cm, A4)": (8.27, 11.69, 780, 730),
}
DEFAULT_TRIM = "6 × 9 in (15.24 × 22.86 cm)"
PAPERS = {"White paper": 2, "Cream paper": 3}   # index into TRIM_SIZES' tuples


def gutter(pages):
    """KDP's minimum inside margin, in inches, for a book of `pages` pages."""
    for limit, inches in ((150, 0.375), (300, 0.5), (500, 0.625), (700, 0.75)):
        if pages <= limit:
            return inches
    return 0.875


@dataclass
class Layout:
    trim: str = DEFAULT_TRIM
    paper: str = "White paper"
    font_size: float = 11
    # Comfortably above KDP's 0.25 in minimums, with room for the running head.
    outside: float = 0.5
    # Added to KDP's minimum gutter: the binding swallows part of the inside
    # margin, so the spine side needs more than the outside to look even.
    binding: float = 0.25
    top: float = 0.75
    bottom: float = 0.75


@dataclass
class Result:
    pages: int
    inside: float   # inside margin used, in inches (KDP's gutter + binding)
    warnings: list


class PrintError(Exception):
    pass


def _runs(para):
    return [{"text": r.text, "b": r.bold, "i": r.italic, "u": r.underline, "s": r.strike}
            for r in para.runs]


def book_data(meta, chapters, options, layout, inside):
    width, height = TRIM_SIZES[layout.trim][:2]
    return {
        "title": meta["title"],
        "author": meta["author"],
        "lang": (meta["language"] or "en").split("-")[0].lower(),
        "year": str(datetime.date.today().year),
        "title_page": options.title_page,
        "chapter_titles": options.chapter_titles,
        "scene_break": export.SCENE_BREAK,
        "layout": {"width": width, "height": height, "inside": inside, "outside": layout.outside,
                   "top": layout.top, "bottom": layout.bottom, "font_size": layout.font_size},
        "chapters": [
            {"title": ch.title,
             "scenes": [[{"kind": p.kind, "align": p.align, "runs": _runs(p)} for p in scene]
                        for scene in ch.scenes]}
            for ch in chapters if ch.scenes
        ],
    }


def page_count(pdf):
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", pdf))


def _compile(data):
    import typst
    try:
        return typst.compile(TEMPLATE.read_bytes(), root=str(TEMPLATE.parent),
                             sys_inputs={"book": json.dumps(data)})
    except typst.TypstError as exc:
        raise PrintError(f"Typesetting failed: {exc}")


def write_kdp_pdf(project, path, options=None, layout=None):
    """Write the interior PDF; returns a Result. Raises PrintError if KDP can't print it."""
    options = options or export.Options()
    layout = layout or Layout()
    chapters = export.collect(project, options)
    meta = {
        "title": project.title,
        "author": project.get_meta("author", "") or "",
        "language": project.get_meta("language", "") or "en",
    }
    if not any(ch.scenes for ch in chapters):
        raise PrintError("There's no text to print yet.")

    # The gutter depends on the page count, which depends on the gutter:
    # lay the book out again until they agree (once or twice in practice).
    minimum = gutter(0)
    for _ in range(5):
        inside = minimum + layout.binding
        pdf = _compile(book_data(meta, chapters, options, layout, inside))
        pages = page_count(pdf)
        if gutter(pages) <= minimum:
            break
        minimum = gutter(pages)

    max_pages = TRIM_SIZES[layout.trim][PAPERS[layout.paper]]
    if pages > max_pages:
        raise PrintError(
            f"This book comes to {pages} pages, but KDP prints at most {max_pages} at "
            f"{layout.trim.split(' (')[0]} on {layout.paper.lower()}. Choose a larger trim size "
            "or a smaller font.")
    warnings = []
    if pages < MIN_PAGES:
        warnings.append(f"KDP prints paperbacks of at least {MIN_PAGES} pages; this one has {pages}.")
    Path(path).write_bytes(pdf)
    return Result(pages, inside, warnings)
