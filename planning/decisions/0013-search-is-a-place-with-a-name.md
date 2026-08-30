# 0013 — Search is a place with a name, not a thing that happens to the tree

Date: 2026-08-30

## Context

Readers reported that the search results look as though they were laid **over**
the tree. They are not: the results and the tree share one slot in the left
column and swap. But nothing on screen said so. The tab strip stood above them
naming the two halves of the documentation, marking neither while the results
held the slot, with both of its own tabs at `aria-selected="false"` and
`tabIndex="-1"` — so during a search the strip was a label for nothing and
unreachable by keyboard. A layer is exactly what that reads as.

A first answer shipped on 2026-08-29 without a record: `showPane()` took the
strip away while the results held the slot, and `resultsHead()` gave them a
head with a title and a close. That removed the strip that marked nothing, and
replaced one oddity with another — the strip now vanished mid-query and the
column changed height under the reader's hand.

Two studies were drawn before deciding, and are kept beside this file:

- `planning/mockups/search-placement.html` — four positions for the results (a
  third tab, the right pane, a popover, a full-width sheet), each measured.
- `planning/mockups/search-tab.html` — the third tab taken as the premise, with
  three answers for where the rows then go.

One number governs the whole question and is worth stating first. A result row
carrying an instance path needs about **1,030 px** before three paths in four
fit whole; the 28 rem tree column gives it **352 px**, at which **0.9 %** of the
schema's 53,691 paths fit and 41 of 60 rows on screen lose the front of theirs.
No arrangement inside the column changes that, and the two that do change it
cost the type page or the whole window. **The truncation is our finding and not
a reader's** — nobody reported it, and paths are cut at the front, so the tail
that tells two occurrences apart survives.

## Decision

The left column has three places, and the strip that names them never leaves.

1. **`Search` is a third permanent tab**, beside `Tree` and `Handbook`. Exactly
   one tab is marked and exactly one is a tab stop, at every moment, whatever
   is showing. The strip is no longer hidden when a schema has no sections;
   the `Handbook` tab is, since one half is not a choice.
2. **The field is that tab's content**, not chrome above the strip. The theme
   button and the `?` it shared a row with are the page's, and move to the far
   end of the strip.
3. **The results head goes.** Where a tab names and marks the region, a head
   under it saying "Results" is a second label for one thing.
4. **The filter chips stay** — one counted line under the field, always there
   while a query stands.
5. **The query forms join the `?`.** The strip that button opens for the tree's
   keys (0010) takes a second line for `type:`, `element:`, `@` and the slash.
   The field's `title` is dropped: it was one of the two weak surfaces this
   replaces. Keys are set as `kbd`, forms as text — a form is typed, not
   pressed.

And one behaviour follows from calling it a place: **opening a result no longer
spends the query.** The click goes to the tree and selects the node, as F14
asks; the Search tab keeps the field, the rows and the count, and carries the
count on its own label while the field is off screen. `Esc` is the one thing
that gives a query up.

## Rationale

The reported confusion is a **labelling** problem, not a geometry one, and it
is answered by naming the region rather than by moving it. Measured on the real
schema at a 1174 × 807 window, the third tab is option A to the pixel — 352 px
of path, 41 of 60 cut, 0.9 % whole — which is what today already costs. The
arrangements that widen the row are still on the table and are still blocked by
the same prior question: whether a result row should carry a name and a count
of its places instead of a path. 53,691 entries are 2,223 distinct element
names, and a name-carrying row needs a fraction of the width, so that decision
moves the requirement by about a factor of three. It is the one to take first;
this one does not prejudge it.

Moving the field inside the tab is what makes the reading stick. With the field
above the strip, something stays while the thing under it swaps, which is the
shape of an overlay. With the field in the tab, typing is something done *in*
the Search tab and the rows appear under the reader's own field.

The syntax and the chips are one switch — `viewer.js` said so in a comment
before either was drawn — but they want different homes, and the study measured
what happens when they share one. As a panel of five explained rows standing
open under the field it cost six of twenty result rows; as a rail beside the
rows in the full-window variant it cost 326 px of path, dropping whole paths
from 71 % to 21 % and eating exactly what that variant is built for; behind a
filter button of its own it cost no row, but put the counts behind a press and
gave the field row a second control. Split, each half is cheap: the chips are
one line and show the counts unasked, and the forms cost nothing at all because
they move into a strip that already exists and that a reader opens once, learns
and closes.

## Consequences

The field is one click away where it was always on screen. `/` answers that for
whoever knows it; the Search tab focuses and selects the field when it is
chosen; and the count on the tab label is what has to carry it for everyone
else. This is the cost of the change and it is worth watching: a reader who
never finds the tab has lost the search entirely.

`showPane()` now takes three names and always marks one. `state.tabs` is gone —
the strip has something to say whatever the schema carries. The two browser
tests that held the shipped 2026-08-29 behaviour are replaced by four that hold
this one, including that the query survives a result click and that the `?`
strip carries both leads.

The `?` now answers for two things at once, which is why its lines are labelled
`Tree` and `Search` rather than running together. If a third thing ever wants
teaching there, the strip is the wrong shape and a panel is the next step.
