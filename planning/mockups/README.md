# Mockups

Design studies for questions that cannot be settled in prose. Not part of the
build, not shipped, and not tested: each is one self-contained HTML file that a
reader opens and clicks. They record what a proposal would look and feel like,
the way `decisions/` records why a question was settled.

A study is superseded by the decision it fed into, and is kept afterwards for
the same reason the decisions are: a later reader who sees only the outcome
assumes it was arbitrary.

## Opening one

Double-click the file, or open it from the browser:

```
planning/mockups/search-placement.html
planning/mockups/search-tab.html
```

No server, no build step, no network — everything is in the file. The web fonts
come from Google Fonts when there is a connection and fall back to the system
faces when there is not; nothing else is loaded from outside.

The `serve` mode is not involved. This is a drawing of the viewer, not the
viewer.

## search-placement.html

**The question.** Readers report that the search results look as though they
were laid over the tree. They are not — the results and the tree share one slot
and swap — but the tab strip above them stood there marking neither half, which
is the reading they were given. The viewer now takes the strip away while the
results hold the slot and gives them a head of their own. What that leaves open
is whether the results belong in the tree column at all. Four positions, one
per option:

* **A — third tab.** The results stay in the column and take a name in the tab
  strip, so exactly one tab is marked at every moment.
* **B — right pane.** The tree stays visible; the results become a document in
  the reading pane.
* **C — popover.** A floating panel anchored under the field, the tree behind
  it.
* **D — full-width sheet.** The field moves into a page header and the results
  open across the whole window.

**How to drive it.** Click A–D or press 1–4. Type in the field, or press `/` to
reach it, or use the three sample queries. Press a result and the tree expands
its path and selects the node, as F14 asks. `Esc` closes. **`R` runs the
ruler**, which marks on every row how many pixels of path it cannot show.

**What is real in it.** The frame is the viewer at its own scale — 1174 × 807
CSS px, a 28 rem tree column, the same type scale and palette — rendered at
100 % and then scaled as one piece to fit the window, so every width read off
it is a width a reader gets. The rows are the schema's own: `segment` returns
exactly the sixty entries out of 21,496 that the viewer returns, with the same
filter counts. Anything typed other than the three sample queries searches only
the rows the file carries, and its counts are that much smaller.

The four gauges under the frame are measured from the DOM on every switch, not
written in by hand:

| | Room for the path | Rows cut off | Whole paths in the schema | Rows without scrolling |
|---|---|---|---|---|
| A third tab | 352 px | 41 of 60 | 0.9 % | 20 |
| B right pane | 529 px | 35 of 60 | 5.6 % | 19 |
| C popover | 257 px | 44 of 60 | 0.3 % | 9 |
| D full-width | 1,031 px | 6 of 60 | 71 % | 19 |

"Whole paths in the schema" is the share of all 53,691 instance paths that
would fit in that row without truncation, computed from the real distribution
of path lengths (median 140 characters, p90 194, longest 270).

**What it is not.** The detail panel inside the frame is context, not subject:
its type page is the root element's and does not change with the selection.
Neither the tree nor the handbook is functional beyond what a click on a result
needs.

**Two things the drawing made visible** that the prose had not:

1. C is worse than it reads. Anchored to the field the panel is 373 px wide,
   which leaves 257 px for a path — less than the column it covers — and the
   filter chips wrap onto two lines.
2. A and the results head are alternatives, not companions. Where the tab strip
   names the results, a head below it saying "Results" is the second label for
   the same thing, and the mockup drops it.

**Measured** 2026-08-29 against CPACS 3.5.1-RC: 58,919 search entries, 53,691
instance paths, 1,206 types. The figures in `../ToDos.md` come from the same
pass.

To pick the question up again later, `search-placement.prompt.md` beside this
file carries the status, the recommendation on record and the commands that
reproduce every figure.

## search-tab.html

**Superseded by `../decisions/0013-search-is-a-place-with-a-name.md`**, which
took this study's premise and its first variant. Kept, as the decisions are, so
a later reader can see that the outcome was chosen and not stumbled into.

**The question.** `search-placement.html` treats the third tab as one position
among four and measures it against the other three. This study takes it as the
premise instead and asks what follows: if search is a tab, the field belongs
inside it, and the query syntax — `type:`, `element:`, `attribute:`, a leading
`@`, a slash for a path — needs somewhere to be read. `../ToDos.md` says that
syntax has two weak teaching surfaces today, a line under the chips that only
an already-narrowing reader ever sees and the field's `title`.

**What the premise fixes**, in all three variants and independently of them:

* Three permanent tabs — `Tree`, `Handbook`, `Search`. None appears or vanishes
  mid-query, so the strip stops changing width under the reader's hand, which
  is the second half of the confusion that `showPane()` answered in `main`.
* The field is the Search tab's content, not chrome above the strip. The `◐`
  and `?` it shared a row with are page chrome and move to the strip's far end.
* **The chips stay, counted, on one line under the field** — All, Elements,
  Types, Attributes. Pressing one writes its form into the field, so the chips
  and the prefixes are one switch and cannot disagree; the counts say what each
  kind would leave without the reader having to open anything.
* **The syntax joins the `?`.** The strip that button already opens for the
  tree's keys (0010) gains a second line for the query forms, set as text
  rather than as `kbd` keys so nobody looks for a key labelled `type:`. **No
  new button anywhere**, and no second `?`.
* A query survives the click that opens a result. The result goes to the Tree
  tab, as F14 asks; the Search tab keeps its rows and says how many on its
  label.

**Three variants, for where the rows go:** T1 in the tab panel, T2 with the
query and its chips in the column and the rows in the reading pane, T3 with the
Search tab taking the whole window.

**How to drive it.** Press 1–3 for the variants, `/` for the field, `?` for the
strip, `R` for the ruler. `Esc` shuts the strip, then clears the query. The
four query chips above the frame cover the plain and the prefixed forms. Press
a result and the Tree tab opens on it — then press `Search` again and the rows
are still there.

The gauges are measured from the DOM on every switch, as in the study above:

| | Room for the path | Rows cut off | Whole paths in the schema | Rows without scrolling |
|---|---|---|---|---|
| T1 rows in the column | 352 px | 41 of 60 | 0.9 % | 18 |
| T2 console left, rows right | 529 px | 35 of 60 | 5.6 % | 20 |
| T3 the tab takes the window | 1,031 px | 6 of 60 | 71 % | 19 |

**What the drawing made visible**, and what the prose would not have:

1. **The tab changes the reading, not the geometry.** T1 lands on option A's
   numbers to the pixel, T2 on option B's, T3 on option D's. Naming a column
   does not widen it, so the grouping question in `../ToDos.md` remains the
   decision that moves this by a factor of three.
2. **Teaching the syntax and switching the kind want different homes.** Three
   arrangements were drawn and measured before this one, and each failed
   differently. As one panel of explained rows standing open under the field it
   cost **six of twenty rows** in T1 and, as a rail beside the rows in T3,
   **326 px** of path — dropping whole paths from 71 % to 21 %, eating exactly
   what T3 is built for. As a panel hanging off its own filter button it cost
   no row, but the counts went behind a press and the field row carried a
   second control. Split in two it is cheap on both sides: the chips are **one
   line** and carry the counts unasked, and the syntax costs nothing at all
   because it moves into a strip that already exists and that a reader opens
   once, learns and closes. Opening that strip costs four rows in T1 and none
   in T2 or T3 — in T2 because it opens in a column the rows do not stand in.
3. **T2 is the only variant whose rows need a head of their own**, because it
   is the only one where they stand in a region the tab does not name. In T1
   and T3 a head under the tab would be the second label for one thing — the
   same finding the study above records for option A.

**What is real in it.** As above: the frame is 1174 × 807 CSS px at the
viewer's own scale, and the rows are the schema's. The query language is parsed
the way `viewer.js:parseQuery` parses it, and nothing is added to it. Counts
are the real ones for `segment`, `wing`, `uid` and their prefixed forms;
anything else searches the rows the file carries and turns the count red to say
so. One fidelity gap to know about: a prefixed query filters the sixty rows
this file holds rather than returning sixty rows of that kind, so `type:wing`
shows 15 of 92 where the viewer would show 60.

**Measured** 2026-08-30 against the same corpus, in Chrome over the DevTools
protocol at a 1174 × 807 frame.
