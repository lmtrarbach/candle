// Print interior for Amazon KDP paperbacks. candle/kdp.py fills in
// sys.inputs.book (JSON): the text is data, never Typst markup, so nothing a
// writer types can change the layout.

#let book = json(bytes(sys.inputs.book))
#let L = book.layout

#set document(title: book.title, author: if book.author != "" { book.author } else { () })
#set text(font: ("Libertinus Serif", "New Computer Modern"), size: L.font_size * 1pt,
          lang: book.lang, hyphenate: true)
#set par(justify: true, leading: 0.62em, spacing: 0.62em,
         first-line-indent: 1.2em)

// -- Which pages get a running head and a page number -----------------------
// Chapters open on a right-hand page, so a chapter may leave the page before
// it blank; blank pages, the front matter and chapter openings stay bare.
#let starts() = query(<chapter-start>).map(m => m.location().page())
#let ends() = query(<chapter-end>).map(m => m.location().page())
#let is-blank(p) = ends().zip(starts()).any(((e, s)) => e < p and p < s)
#let body-started(p) = starts().len() > 0 and p >= starts().first()

#set page(
  width: L.width * 1in, height: L.height * 1in,
  margin: (inside: L.inside * 1in, outside: L.outside * 1in,
           top: L.top * 1in, bottom: L.bottom * 1in),
  header: context {
    let p = here().page()
    if body-started(p) and not is-blank(p) and p not in starts() {
      set text(size: 0.8em, tracking: 0.08em)
      if calc.even(p) { align(left, upper(if book.author != "" { book.author } else { book.title })) }
      else { align(right, upper(book.title)) }
    }
  },
  footer: context {
    let p = here().page()
    if body-started(p) and not is-blank(p) {
      set text(size: 0.85em)
      align(center, counter(page).display())
    }
  },
)

// -- Text -----------------------------------------------------------------
#let run(r) = {
  let c = [#r.text]
  if r.b { c = text(weight: "bold", c) }
  if r.i { c = emph(c) }
  if r.u { c = underline(c) }
  if r.s { c = strike(c) }
  c
}

// A scene's first paragraph isn't indented, as in printed books.
#let para(p, first: false) = {
  let body = p.runs.map(run).join()
  if p.kind in ("h1", "h2", "h3") {
    // Headings inside a scene: set apart, not part of the book's outline.
    block(above: 1.2em, below: 0.8em, align(center, text(weight: "bold", body)))
  } else if p.kind == "ul" {
    list(body)
  } else if p.kind == "ol" {
    enum(body)
  } else if p.align == "center" {
    align(center, par(first-line-indent: 0em, body))
  } else if p.align == "right" {
    align(right, par(first-line-indent: 0em, body))
  } else if first {
    par(first-line-indent: 0em, body)
  } else {
    par(body)
  }
}

#let scene-break = block(above: 1.1em, below: 1.1em, width: 100%,
                         align(center, book.scene_break))

// -- Front matter ---------------------------------------------------------
#if book.title_page {
  v(28%)
  align(center, text(size: 2.2em, book.title))
  if book.author != "" {
    v(1.5em)
    align(center, text(size: 1.2em, book.author))
  }
  pagebreak()
  // Copyright page, on the back of the title page.
  set text(size: 0.8em)
  set par(justify: false, first-line-indent: 0em)
  v(1fr)
  [Copyright © #book.year #if book.author != "" [#book.author] else [the author]. All rights reserved.]
}
#metadata(none) <chapter-end>

// -- Chapters -------------------------------------------------------------
#for (i, ch) in book.chapters.enumerate() {
  pagebreak(to: "odd", weak: true)
  if i == 0 { counter(page).update(1) }
  [#metadata(ch.title) <chapter-start>]
  // The page it opens on, for checking the layout (tests query it).
  context [#metadata(here().page()) <chapter-page>]
  v(18%)
  if book.chapter_titles and ch.title != "" {
    align(center, text(size: 1.5em, ch.title))
  }
  v(2.5em)
  ch.scenes.map(s => s.enumerate().map(((k, p)) => para(p, first: k == 0)).join(parbreak()))
    .join(scene-break)
  [#metadata(none) <chapter-end>]
}
