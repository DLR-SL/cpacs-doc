# 0015 — Borrowed words say whose they are

Date: 2026-08-30

## Context

A node's detail panel carries two kinds of text: what the schema says about
this place, from the element declaration, and what it says about the type
standing there. `.cd-elementdoc` and `.cd-summary` were set alike — `--step-3`,
`line-height: 1.5` — and the only boundary between them was the `Type:` line.

Measured on the real schema over all 54,552 nodes: 41,004 (75.2 %) carry both
kinds, 12,980 (23.8 %) only the type's, 387 only their own, 181 neither. So on
99 % of nodes a reader is looking at words whose owner the panel did not name,
and on the 12,980 a general sentence — "Mass description", "Point with
global/local reference" — reads as a statement about this place.

This is the same gap the Sandcastle build papers over with
`useTypeDocumentation`, which we declined (see `planning/ToDos.md`): there the
type's words are substituted for the element's without a word about it.

## Decision

What belongs to the place stays unmarked. What the type lends stands in a
`section.cd-borrowed`, opened by one line — `About the type <name>`, the name
being the link into the type — with a short tick beside that line. The prose
itself keeps the margin and the measure the place's own words have.

The `Type:` line is gone from the head. The type is named where its words
begin; where it has none to lend — 568 nodes — the head names it instead, so it
is never nameless. The value type keeps its place in the head, since what may
be written at this place is a fact about the place.

The tables stay outside the rail: they answer what may stand here, and their
headings scope them. On the type's own panel nothing is marked, because
everything there is the type's.

## Rationale

**Only one of the two is marked.** Marking both would make a reader learn two
signs where one will do, and the unmarked one is the reading a beginner wants
anyway: this is the thing in front of me. The rule generalises to the tables,
where the Description column is the element's own text and carries no mark.

**The mark opens the block; it does not fence it.** A rail down the side was
built first and read as a quotation: on `wingSectionType` and its like the
type's words are the substance of the panel — four paragraphs and a figure —
and indenting them behind a line makes an aside of the main thing. What
changes at that point is the owner, not the standing of the text, so the mark
sits where the change is.

**The tick is decoration; the attribution carries the meaning.** A screen
reader hears "About the type pointAbsRelType" before the prose, and nothing
here depends on seeing a mark or a colour.

**Alternatives, drawn on real content and compared in a browser**
(`planning/` carries no mockup; it was a scratch file, the way the search
mockups were):

* *A rail down the whole block.* Shipped first and taken out again: see above.
* *A rail that fades out after a few lines.* Keeps the indent without the
  fence, and the indent then stands unexplained for the rest of the block.
* *The attribution alone, set as a small-caps label.* Nothing to see at a
  glance; on the 12,980 nodes that carry only the type's words there is no
  unmarked paragraph beside it for the eye to compare against.
* *The owner in the margin, both blocks labelled.* The most elegant on a wide
  page and measurably wrong here: the detail pane is 718 px, under the 52 rem
  the gutter needs, so in the viewer it would almost always fold above the text
  and be the first alternative with extra lines.

**One stroke in, two strokes out.** The head carried two rules within 120 px,
one under the occurrence line and one under the type line, cutting it into
three blocks. The type line is gone, and the rule under the remaining line went
with it: it only separated, which the space between them already does. Counted
in a browser on the panel of `translation`, the tick is 1 stroke of 50 — the
tables draw 48 of them, 12 column heads and 36 row rules — and it is the only
one in the reading part of the page, an em tall rather than the height of the
text. The same rule sat on the static type
pages, whose head reads the same way, so it went there too.

## Consequences

`appendTypeBody` is split: `appendTypeProse` and `appendTypeTables`, with the
node panel calling the prose through `appendBorrowedProse` and the type panel
calling both unmarked.

`tests/test_viewer_provenance.py` holds it in a browser on
`fixtures/provenance.xsd`, which puts a node in each of the three cases: the
place's words stand outside the block, the block names its owner and links to
it, the tables are not inside it, a type with nothing to lend is still named,
and the type's own panel marks nothing.

Three tests in `test_viewer_types.py` held the old `Type:` line and now read
the head line, which says the same thing in the shape it now has.

What this does not do is tell a reader whether the type's words are *apt* for
this place. Where they are a placeholder — 393 of the 1,089 documented types
have their own name as their summary — the panel now says plainly that a
general text is being shown, which is the honest half of the answer. The other
half is documentation written at the element, which is a schema matter.
