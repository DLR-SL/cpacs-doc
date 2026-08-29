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

## Rebuilding this one

The file is generated: a template carries the markup, the styles and the
behaviour, and the sixty rows per query plus the path-length distribution are
injected into it from a model built by the extractor. The generator is not kept
in the repository — it is a dozen lines against `cpacs-doc build`, and the
study is finished. Edit the HTML directly; the data in it is a literal.
