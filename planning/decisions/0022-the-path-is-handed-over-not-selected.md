# 0022 — The path is handed over, not selected

Date: 2026-09-02

## Context

The breadcrumb above the detail panel is how a reader says where something is
when writing to someone else. It is built as one button per segment with a
` / ` text node between them, so selecting the line with the mouse yields
`cpacs / header / name` — the separators padded with spaces, which is not a
path and has to be repaired by hand at the other end.

## Decision

- A `copy` button stands at the right end of the breadcrumb and puts the path
  on the clipboard as an absolute XPath: `/cpacs/header/name`.
- The string is built from the model, not read off the screen, and its root
  comes from the tree's declaration — the same source `select()` uses for the
  URL — rather than from the word written in the first crumb.
- No positional predicates.
- Where the clipboard refuses, the button says so.

## Rationale

**No `[1]`.** The tree is the schema's and not a document's, so there is no
index to state. Writing `/cpacs/vehicles/aircraft/model[1]/wings/wing[1]` would
make an assertion about an instance nobody here has seen, and a reader pasting
it into a tool would get an answer about the first of something rather than an
error about a path that cannot be resolved. This is the project's standing
rule — report, do not repair — applied to a string.

**A fallback, because the deployment is not a secure context.**
`navigator.clipboard` is undefined over plain http, which is how this is
served on an intranet, so the older selection-and-`execCommand` path stands
behind it. The field it needs must be in the document to be selected, so it is
put off screen rather than hidden: `display: none` cannot be selected from.

**Saying "copied" when nothing was copied is the one unrecoverable answer.**
The reader goes to the mail and pastes whatever was there before. So the
failure is written on the button — `not copied` — and no way round it is
offered, because there is none to offer: nothing is selected for the reader to
copy by hand. The path is on the button's `title` either way.

**The word, not a glyph.** The same trade as 0021, and the same reason: a
glyph from a system fallback is legible here and not dependably legible
everywhere. It keeps the nav's uppercase, which is what distinguishes a label
from the code-face path beside it, and it takes a hairline and the muted ink
rather than the crumbs' underline in `--link` — a crumb is a place to go and
this is not.

**Not the mask icon either, though it would have worked.** The viewer already
draws icons without a font: `.cd-group-mark` and `.cd-theme-mark` are 16×16
SVGs as `mask-image`, painted in the surrounding ink, so the fallback problem
that rules out a glyph does not apply to one. Two things decided against it.
Where masks are unsupported nothing is drawn — which those marks survive
because the wording stands beside them, and a button whose only content is the
icon would not; keeping the word as hidden text to cover that puts the label
back in the markup regardless. And an icon has to be guessed, which moves the
explaining onto the `title`, the one place a reader looks only once he has
already wondered. This button is read once and used from then on, so the width
an icon saves is not worth the wondering.

## Consequences

Only the tree node's breadcrumb has it. The type page and the documentation
section carry a `← back` crumb and no instance path, so there is nothing there
to hand over.

Measured on the real schema at
`/cpacs/vehicles/aircraft/model/wings/wing/sections/section/elements/element`,
ten segments: the button hands over that path exactly, and the line wraps
rather than overflowing — 0 px sideways at the default panel width of 628 px
and still 0 at 102 px, where the nav is 222 px tall and the button stays
inside the panel.

Held in a browser by `tests/test_viewer_breadcrumb.py`: the XPath for a deep
path and for the root alone, the word the button shows before and after, the
refusal, and the `title`. The clipboard itself is the browser's and reading it
back wants a permission the driver does not grant, so what is asserted is the
string handed to `writeText`.
