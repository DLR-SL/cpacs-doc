# 0017 — The tree explains itself in one place, and not on hover

Date: 2026-09-01

## Context

Two things in the tree cannot be read off it: its keys, and its marks. 0010
settled the keys and said they are "said once in a strip above it". That strip
had grown into a legend of five entries and eight key caps, wrapping onto three
lines above a tree, standing there from the first paint. Readers went past it,
which is what a reader does with furniture.

The marks were explained the other way, on hover: the `⑂` on a choice node
carried a tip. That cost the tree both scrollbars. Measured on
`fixtures/minimal.xsd` — the smallest schema there is, five marks — with every
node open:

| | scrollHeight / clientHeight | scrollWidth / clientWidth |
| --- | --- | --- |
| with the tips | 272 / 219 | 445 / 433 |
| with the tips removed | 219 / 219 | 448 / 448 |

This is 0014's finding one pane over: a tip is laid out even while hidden, so
it belongs to its pane's scrollable area whether or not anyone has opened it.
0014 met it in the type pages' tables and answered with `overflow-y: clip`;
0014's consequences say the viewer's panel is not part of it, and the tree was
not considered at all. `.cd-pane` carries `overflow: auto`, so the tip a reader
did open was also cut at the pane's edge — 53 px below it at the default tree
width, 180 px past its right at half that.

## Decision

- The tree's marks are explained in a legend under the `?`, not on hover. The
  `⑂` stays on the row; no tip does.
- The hint that appears by itself is one line — `↑ ↓ move`, `Enter details`,
  `more under ?` — and it appears at the reader's first click in the tree, not
  at page load. A tree key before that click calls it off for good.
- The full table stays behind the `?`, with the legend as a second row under a
  dividing rule.
- The legend's samples are drawn in the tree's own classes, so restyling the
  tree restyles the legend.
- A heading names what its row is, never where the reader is. `Tree` and
  `Search` are gone; `Legend` and `Start your search with:` remain.

## Rationale

**A hover tip cannot start anything.** It needs a pointer already on the thing,
so it can confirm what a reader has begun and never begin it; on touch it does
not exist at all. It also explains one row at a time, to whoever already
suspected there was something to explain.

**The timing, not the wording, was what made the strip furniture.** Standing
there from the first paint it is part of the frame. After the reader's first
click it answers the one question he has, which is what now. So it can also be
short: one line of 37 px against the table's 65, three caps against eight.

**Repositioning the tip was the alternative and is more machinery for less.**
Escaping `.cd-pane`'s clipping means `position: fixed` and placing the box from
script on every hover and focus, for an explanation that reads better in one
place than in fifty.

**The heading rule follows from removing `Tree` and `Search`.** The tab above
already lights up; a line reading "Tree" under the Tree tab said nothing twice.
What is left to name is a row whose kind is not written on it — the forms, since
a key in relief is plainly pressed and `type:` in the code face is plainly typed
only to someone who already knew. So that heading is the sentence the forms
finish.

## Consequences

This revises 0010's consequence that the keys are "said once in a strip above
it": they are said once at the reader's first touch of the tree, and the strip
behind the `?` is where the rest lives. Nothing else in 0010 changes.

Nothing was lost for screen readers. `Accessibility.getFullAXTree` reports no
`role="note"` among the page's 317 nodes, so the tip's `visibility: hidden` had
kept it out of the accessibility tree all along — contrary to the comment that
sat on the rule and claimed the opposite.

Drawing the legend from the tree's rules found a second fault in them.
`.cd-required .cd-name` set only the weight and inherited its ink, so outside
the tree the "must appear" sample came out in the muted colour of its opposite.
The rule states the colour now, as its optional twin always did.

The heading moved from a 3.4 rem column beside its row to a line of its own
above it, which is also what tells it from the samples, together with the text
face against the code face and `--ink-soft` against `--ink`: on weight alone it
sat within 50 of the legend's own bold sample. It is not set in capitals,
because it holds a word on one line and a sentence on the next.

The dividing rule between the two tree rows had been written long before and
was drawing nothing: the Search group stood between them in the document, so
`.cd-hint-line[hidden] + .cd-hint-line` suppressed it — correctly, and
invisibly. The legend stands directly after the keys now.

Held in a browser by `tests/test_viewer_keyboard.py` (0011): the tree gains no
scroll from its marks; the hint waits for the click and stays away from a reader
already on the keys; the opening holds one row at the tree's default width; the
legend is drawn as the tree draws it; the heading has a row to itself; and the
rule between the two is `1px solid var(--rule)`.
