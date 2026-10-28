import json
import re

import pytest
import typst

from candle import export, kdp
from candle.db import Project

PARA = "<p>" + "The wind came off the sea in long grey ribbons, and Marta climbed the steps. " * 12 + "</p>"


def make_book(path, chapters=2, paras=3, title="Storm Book", text=PARA):
    p = Project.create(path, title, "A. Writer")
    first = p.list("chapters")[0]["id"]
    for c in range(chapters):
        ch = first if c == 0 else p.insert("chapters", title=f"Night {c + 1}")
        scene = p.list("scenes", chapter_id=ch)[0]["id"] if c == 0 else p.insert("scenes", chapter_id=ch)
        p.save_scene_content(scene, text * paras, "x")
    return p


def media_box(pdf):
    return re.search(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf).groups()


@pytest.mark.parametrize("pages,inches", [(24, 0.375), (150, 0.375), (151, 0.5), (300, 0.5),
                                          (301, 0.625), (500, 0.625), (501, 0.75), (700, 0.75),
                                          (701, 0.875), (828, 0.875)])
def test_gutter_follows_kdp_table(pages, inches):
    assert kdp.gutter(pages) == inches


def test_interior_is_trim_size_with_kdp_margins(qapp, tmp_path):
    book = make_book(tmp_path / "b.candle", paras=10)
    out = tmp_path / "b.pdf"
    result = kdp.write_kdp_pdf(book, out)
    pdf = out.read_bytes()
    assert media_box(pdf) == (b"432", b"648")                    # 6 × 9 in, no bleed
    assert result.pages == kdp.page_count(pdf)
    assert result.inside == kdp.gutter(result.pages) + kdp.Layout().binding
    assert result.warnings and "at least 24" in result.warnings[0]   # a two-chapter test book

    small = kdp.write_kdp_pdf(book, out, layout=kdp.Layout(trim="5 × 8 in (12.7 × 20.32 cm)"))
    assert media_box(out.read_bytes()) == (b"360", b"576")
    assert small.pages > result.pages


def test_long_books_get_a_wider_gutter(qapp, tmp_path):
    book = make_book(tmp_path / "b.candle", chapters=20, paras=20)
    result = kdp.write_kdp_pdf(book, tmp_path / "b.pdf")
    assert result.pages > 150
    assert result.inside == kdp.gutter(result.pages) + 0.25 > 0.375 + 0.25
    assert not result.warnings


def test_chapters_open_on_right_hand_pages(qapp, tmp_path):
    book = make_book(tmp_path / "b.candle", chapters=4, paras=4)
    options = export.Options()
    data = kdp.book_data({"title": "T", "author": "A", "language": "en"},
                         export.collect(book, options), options, kdp.Layout(), 0.625)
    pages = json.loads(typst.query(kdp.TEMPLATE.read_bytes(), "<chapter-page>", field="value",
                                   sys_inputs={"book": json.dumps(data)}))
    assert len(pages) == 4
    assert pages[0] == 3                        # after the title page and its copyright back
    assert all(p % 2 == 1 for p in pages)       # odd = right-hand page


def test_text_is_never_typst_code(qapp, tmp_path):
    tricky = "<p>#pagebreak() #set page(width: 1in) $x^2$ *bold* _it_ = Heading [link] @ref \\ // c</p>"
    book = make_book(tmp_path / "b.candle", title="#panic(\"boom\") *T*", text=tricky)
    plain = make_book(tmp_path / "p.candle", title="Plain", text="<p>" + "x" * len(tricky) + "</p>")
    a = kdp.write_kdp_pdf(book, tmp_path / "a.pdf")
    b = kdp.write_kdp_pdf(plain, tmp_path / "b.pdf")
    assert a.pages == b.pages
    assert media_box((tmp_path / "a.pdf").read_bytes()) == (b"432", b"648")


def test_too_long_for_kdp_is_refused(qapp, tmp_path, monkeypatch):
    book = make_book(tmp_path / "b.candle")
    monkeypatch.setitem(kdp.TRIM_SIZES, kdp.DEFAULT_TRIM, (6, 9, 4, 4))
    with pytest.raises(kdp.PrintError, match="at most 4"):
        kdp.write_kdp_pdf(book, tmp_path / "b.pdf")
    assert not (tmp_path / "b.pdf").exists()


def test_empty_book_is_refused(qapp, tmp_path):
    book = Project.create(tmp_path / "e.candle", "Empty", "")
    with pytest.raises(kdp.PrintError, match="no text"):
        kdp.write_kdp_pdf(book, tmp_path / "e.pdf")
