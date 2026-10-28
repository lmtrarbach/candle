"""Convert editor (Qt rich text) content into a small, clean paragraph model
that every exporter and the paste sanitizer render from."""

import html
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextDocument, QTextListFormat

ORDERED_STYLES = {
    QTextListFormat.Style.ListDecimal,
    QTextListFormat.Style.ListLowerAlpha,
    QTextListFormat.Style.ListUpperAlpha,
    QTextListFormat.Style.ListLowerRoman,
    QTextListFormat.Style.ListUpperRoman,
}


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False


@dataclass
class Para:
    kind: str = "p"          # p | h1 | h2 | h3 | ul | ol
    align: str = "left"      # left | center | right | justify
    runs: list = field(default_factory=list)

    @property
    def text(self):
        return "".join(r.text for r in self.runs)


def _align(flags):
    if flags & Qt.AlignmentFlag.AlignHCenter:
        return "center"
    if flags & Qt.AlignmentFlag.AlignRight:
        return "right"
    if flags & Qt.AlignmentFlag.AlignJustify:
        return "justify"
    return "left"


def parse(rich_html):
    """Parse Qt/HTML rich text into a list of Para."""
    doc = QTextDocument()
    doc.setHtml(rich_html or "")
    return parse_document(doc)


def parse_document(doc):
    paras = []
    block = doc.begin()
    while block.isValid():
        fmt = block.blockFormat()
        kind = "p"
        if fmt.headingLevel():
            kind = f"h{min(fmt.headingLevel(), 3)}"
        elif block.textList():
            kind = "ol" if block.textList().format().style() in ORDERED_STYLES else "ul"
        para = Para(kind, _align(fmt.alignment()))
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                cf = frag.charFormat()
                para.runs.append(Run(
                    frag.text().replace(" ", "\n").replace("￼", ""),
                    cf.fontWeight() >= QFont.Weight.Bold and kind[0] != "h",
                    cf.fontItalic(),
                    cf.fontUnderline(),
                    cf.fontStrikeOut(),
                ))
            it += 1
        paras.append(para)
        block = block.next()
    return paras


def non_empty(paras):
    return [p for p in paras if p.text.strip()]


# -- renderers ---------------------------------------------------------------

def _run_html(run):
    text = html.escape(run.text).replace("\n", "<br/>")
    if run.bold:
        text = f"<strong>{text}</strong>"
    if run.italic:
        text = f"<em>{text}</em>"
    if run.underline:
        text = f"<u>{text}</u>"
    if run.strike:
        text = f"<s>{text}</s>"
    return text


def to_html(paras, heading_offset=0):
    """Well-formed (XHTML-safe) HTML fragment."""
    out = []
    open_list = None
    for p in paras:
        if p.kind in ("ul", "ol"):
            if open_list != p.kind:
                if open_list:
                    out.append(f"</{open_list}>")
                out.append(f"<{p.kind}>")
                open_list = p.kind
            out.append(f"<li>{''.join(_run_html(r) for r in p.runs)}</li>")
            continue
        if open_list:
            out.append(f"</{open_list}>")
            open_list = None
        tag = p.kind
        if tag.startswith("h"):
            tag = f"h{min(int(tag[1]) + heading_offset, 6)}"
        style = f' style="text-align: {p.align}"' if p.align != "left" else ""
        out.append(f"<{tag}{style}>{''.join(_run_html(r) for r in p.runs)}</{tag}>")
    if open_list:
        out.append(f"</{open_list}>")
    return "\n".join(out)


def _md_escape(text):
    for ch in "\\*_`[]~#":
        text = text.replace(ch, "\\" + ch)
    return text


def _run_md(run):
    text = _md_escape(run.text).replace("\n", "  \n")
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    if run.strike:
        stripped = f"~~{stripped}~~"
    if run.italic:
        stripped = f"*{stripped}*"
    if run.bold:
        stripped = f"**{stripped}**"
    return lead + stripped + trail


def to_markdown(paras, heading_offset=0):
    out = []
    number = 0
    for p in paras:
        body = "".join(_run_md(r) for r in p.runs)
        if p.kind.startswith("h"):
            out.append("#" * min(int(p.kind[1]) + heading_offset, 6) + " " + body)
            number = 0
        elif p.kind == "ul":
            out.append(f"- {body}")
        elif p.kind == "ol":
            number += 1
            out.append(f"{number}. {body}")
        else:
            out.append(body)
            number = 0
    # Blank line between blocks, but keep list items together.
    result = []
    for i, line in enumerate(out):
        if i and not (paras[i].kind in ("ul", "ol") and paras[i - 1].kind == paras[i].kind):
            result.append("")
        result.append(line)
    return "\n".join(result)


def to_text(paras):
    return "\n\n".join(p.text for p in paras)
