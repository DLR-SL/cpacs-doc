# 0018 — Two keys commit, one key comes back

Date: 2026-09-02

## Context

Readers split over what Enter should do. Some want it to hand the keyboard to
the detail panel, as F1 asks; others want to keep moving in the tree and still
see the detail page change. Both were already served: 0010 gave Space to the
one and Enter to the other, and `test_space_selects_without_leaving_the_tree`
has held that apart since.

Nothing said so. The table behind the `?` listed `↑ ↓`, `→ ←`, `Enter`, `/` and
`Esc ←`; the one-line opening of 0017 listed `↑ ↓`, `Enter` and `more under ?`.
Space appeared in neither, so the reader who wanted to stay in the tree had the
key and no way to learn it, and asked for a key that was already under his
thumb.

0016 also gave ArrowLeft to the detail panel as a second way back. It never
held for long: it was claimed only on an event the panel itself received, so it
was gone the moment the reader tabbed on to a link, and Escape had to be
learned anyway. What it cost is a key the panel has use for. 0014 settled that
a wide table scrolls rather than the page, and the panel's own tables are the
open case — `wingType`, `fuselageType` and `genericMassType` each need 1,110 px
in a 718 px pane, 376 px of sideways scroll, measured 2026-08-30 at 1280 × 900.

## Decision

- The table behind the `?` names both keys that commit, and their captions say
  what separates them: `Space` `details`, `Enter` `details, and go there`.
- The opening names `Space`, not `Enter`. It stays three entries on one line.
- The detail panel claims no key of its own. Escape is the way back, from
  anywhere inside it; `←` and `→` are the panel's.

## Rationale

**The keys were not the gap; the naming was.** A second key for the second
group is what was asked for, and it has existed since 0010. What the reader
could not do is find it: the tree is the one control here whose keys cannot be
read off it (0017), so a key that is not in the hint does not exist.

**Both captions, or neither says anything.** `details` on both lines would make
the second line look like a restatement of the first. The pair differs only in
where the keyboard is left standing, which is not visible on screen — 0016 made
that state legible once it had happened, and the table is where it is named
before it happens.

**Space is free in a single-select tree.** The WAI-ARIA APG assigns it only in
multi-select trees ("Space: Toggles the selection state of the focused node")
and gives Enter the activating role, which in a single-select tree "is
typically to select the focused node". Binding Space to a select that does not
move the focus adds to that pattern rather than colliding with it. Its browser
default, scrolling the page, is already suppressed in the tree's handler, and
neither pane scrolls the page anyway.

**One reliable way back beats two unreliable ones.** ArrowLeft covered exactly
the state Enter leaves behind and no other. A reader cannot tell that state
from the one after a Tab, so the key that works "sometimes, depending on where
you are in the panel" is a key that has to be tried. Escape works from every
one of those places, including the search field and the hint.

**The panel has its own use for the arrow.** Up and Down were already left
alone, because a type page past the fold is read with them; sideways is the
same argument one axis over, and the pane measured above is the case. Nothing
in the tree changes: `←` and `→` still close, open and step in and out there.

## Consequences

`setupDetailKeys()` is gone, and with it the panel's only listener.

The table is six entries and eight caps: `Space` was added and `←` taken off
the way back, so `test_the_question_mark_strip_carries_the_query_forms_too`
counts eight again, as it did before either change. The opening is unchanged in
width — `Space` is as long as `Enter` — and the test that holds it to one row
at the default tree width still passes.

Two browser tests became one: what ArrowLeft did from the panel and what it did
from a link inside it are now the same thing, and the test asserts the panel
keeps the key in both states and that Escape returns to the row Enter was
pressed on.

This supersedes 0016 in its second decision — ArrowLeft stepping out of the
panel — and the rationale under "ArrowLeft only from the panel itself". The
rest of 0016 stands: the cursor's dashed mark, which is what makes the jump
legible, and the `--focus` token. It supersedes 0017 in the wording of the
opening only; the legend, the timing and the placement are unaffected.

F1 is untouched: Enter still focuses the detail panel.
