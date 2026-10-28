import zipfile

import pytest

from candle import export, richtext
from candle.db import Project

SCENE = ("<h2>Arrival</h2><p>It was a <b>dark</b> and <i>stormy</i> night &amp; "
         "the <u>rain</u> fell.</p><p align='center'>Centered</p><ul><li>one</li><li>two</li></ul>")


@pytest.fixture
def project(tmp_path, qapp):
    p = Project.create(tmp_path / "book.candle", "Storm <Book>", "A. Writer")
    ch = p.list("chapters")[0]["id"]
    s1 = p.list("scenes")[0]["id"]
    p.save_scene_content(s1, SCENE, "x")
    s2 = p.insert("scenes", chapter_id=ch, title="second", status="done")
    p.save_scene_content(s2, "<p>Second scene.</p>", "Second scene.")
    ch2 = p.insert("chapters", title="The End")
    s3 = p.insert("scenes", chapter_id=ch2)
    p.save_scene_content(s3, "<p>Fin.</p>", "Fin.")
    yield p
    p.close()


def test_parse_rich(qapp):
    paras = richtext.parse(SCENE)
    assert [p.kind for p in paras] == ["h2", "p", "p", "ul", "ul"]
    bold = [r for r in paras[1].runs if r.bold]
    assert bold and bold[0].text == "dark"
    assert paras[2].align == "center"


def test_markdown(qapp):
    md = richtext.to_markdown(richtext.parse(SCENE))
    assert "## Arrival" in md
    assert "**dark**" in md and "*stormy*" in md
    assert "- one\n- two" in md


def test_html_escapes(qapp):
    out = richtext.to_html(richtext.parse("<p>a &lt;b&gt; &amp; c</p>"))
    assert out == "<p>a &lt;b&gt; &amp; c</p>"


@pytest.mark.parametrize("fmt", sorted(set(export.FORMATS.values())))
def test_every_format_writes(tmp_path, project, fmt):
    out = tmp_path / f"book.{fmt}"
    export.export(project, str(out), fmt)
    assert out.exists() and out.stat().st_size > 0


def test_markdown_structure(tmp_path, project):
    out = tmp_path / "book.md"
    export.export(project, str(out), "md")
    text = out.read_text()
    assert text.startswith("# Storm <Book>")
    assert "## 1. Chapter 1" in text and "## 2. The End" in text
    assert export.SCENE_BREAK in text


def test_only_done(tmp_path, project):
    out = tmp_path / "book.txt"
    export.export(project, str(out), "txt", export.Options(only_done=True))
    text = out.read_text()
    assert "Second scene." in text and "stormy" not in text


def test_epub_is_valid_zip(tmp_path, project):
    out = tmp_path / "book.epub"
    export.export(project, str(out), "epub")
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert "OEBPS/content.opf" in names and "OEBPS/nav.xhtml" in names
        import xml.dom.minidom
        for name in names:
            if name.endswith((".xhtml", ".opf", ".xml")):
                xml.dom.minidom.parseString(zf.read(name))   # well-formed


def test_docx_content(tmp_path, project):
    import docx
    out = tmp_path / "book.docx"
    export.export(project, str(out), "docx")
    text = "\n".join(p.text for p in docx.Document(str(out)).paragraphs)
    assert "stormy" in text and "Fin." in text
