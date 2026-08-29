# Resuming the search placement work

A briefing for picking this up again, with Claude or without. Dated, because
half of it is a status and a status goes stale: **written 2026-08-29 against
CPACS 3.5.1-RC.** Everything below that is a claim about the code or the schema
is to be re-checked before it is relied on — the reproduction commands are here
so that costs minutes rather than a session.

## Paste this to start

```
Read planning/mockups/search-placement.prompt.md and planning/mockups/README.md,
then open planning/mockups/search-placement.html to see the four options.
The open question is where the search results belong. Tell me what you would
verify first, and do not change anything until we have agreed on the step.
```

## The question

The search results and the tree share one slot in the left column and swap.
Readers reported that the results look as though they were laid *over* the
tree. That reading has been answered (below), but it exposed a second question
that has not been: **whether the results belong in the tree column at all.**

Four positions are drawn in `search-placement.html` — a third tab, the right
pane, a popover, a full-width sheet. The README beside it says what each one
costs, measured.

## What is already done

Shipped in `main` on 2026-08-29, no ADR written for it yet:

* `src/cpacs_doc/assets/viewer.js` — `showPane()` takes the tab strip away
  while the results hold the slot, and the tab marks follow `state.tab` so
  exactly one tab is marked and one tab stop exists at every moment (both were
  `aria-selected="false"` and `tabIndex="-1"` before, so the strip was
  unreachable by keyboard during a search). `resultsHead()` gives the results a
  head with a title and a close. `run()` returns to `state.tab` rather than
  always to the tree.
* `src/cpacs_doc/assets/styles.css` — `.cd-pane-head`, `.cd-pane-title`,
  `.cd-pane-close`, on the tab strip's rule and at its height (35 px both) so
  the swap does not move the list.
* `tests/test_viewer_documentation.py` — two browser tests hold both
  properties.

**Not done:** no decision record for that change; `ToDos.md` still lists the
search items as open.

## The recommendation on record

1. Change nothing further about the position yet. The reported confusion is
   answered; put it in front of readers before stacking a second change on it.
2. Decide the grouping question in `ToDos.md` first — one entry per name with
   its places listed, the way "Used by" lists them. 53,691 entries are 2,223
   distinct element names; `x` alone is 5,280 of them. A row that carries a
   name and a count needs a fraction of the width a row carrying a path needs,
   so this decision moves the placement requirement by about a factor of three.
   Its price is a click on the way into the tree, which is the part of the
   quick search that works well today.
3. Then the position is small: with name-carrying rows, **A** (third tab) is
   enough — and note that A *replaces* the results head shipped above rather
   than joining it, or the region is labelled twice.
4. If the grouping is rejected, **D** (full-width sheet), not B and not C. It
   is the only one that repairs the truncation (71 % against 0.9 %). B buys too
   little for displacing the type page; C fails on its own numbers.

Standing caveat, and it belongs in the discussion: **the truncation is a
finding of ours, not of any reader.** Nobody reported it. Paths are truncated
at the front, so the tail — the part that tells two occurrences apart —
survives. Asking two CPACS users whether the front of a path has ever been
missing is cheaper than any of the four rebuilds.

## Reproducing the numbers

The measurements are all from the real schema and a real browser. Nothing here
needs a package that is not already in the dev group.

```
# the model, once; every corpus figure is computed from this file
uv run cpacs-doc build <cpacs>/schema/cpacs_schema.xsd -o build/ --tolerate-errors

# the viewer, for anything measured on screen
uv run cpacs-doc serve <cpacs>/schema/cpacs_schema.xsd --port 8123
```

`<cpacs>` is a checkout of the CPACS repository; `cpacs-doc` carries no schema
of its own. Note that `--tolerate-errors` exists on `build` and `report` but
not on `serve`.

Widths, row counts and anything else on screen are read from the page itself:
`tests/cdp.py` drives an installed Chrome or Edge over the DevTools protocol
without a driver package. `browser.open(base + "/tree/")` reaches the viewer —
`/` serves the index, not the viewer, and a tree path is what the router
answers.

Figures as measured on 2026-08-29, at a 1174 × 807 viewport with the tree
column at its 28 rem default:

| | Room for the path | Rows cut off | Whole paths of 53,691 |
|---|---|---|---|
| today, and A | 352 px | 41 of 60 | 0.9 % |
| B right pane | 529 px | 35 of 60 | 5.6 % |
| C popover | 257 px | 44 of 60 | 0.3 % |
| D full width | 1,031 px | 6 of 60 | 71 % |

Corpus: 58,919 search entries — 53,691 instance paths, 1,206 types, 4,022
attributes. Path lengths: median 140 characters, p90 194, longest 270. A broad
query is the normal case: `segment` matches 21,496 entries, `wing` 8,218.

## How the work is expected to go

Answers in German, artefacts and code in English. Minimal diffs and no
unrelated reformatting; comments name an architectural necessity, not a
debugging narrative. One step at a time, each put up for review before the
next. Numbers are measured against the real schema rather than estimated, and a
claim about the schema or about another tool is checked and cited. Where a
proposal turns out to conflict with the project's "report rather than repair"
principle, say so and withdraw it rather than shipping the guess.

## Where to look

* `planning/mockups/README.md` — the study, what is real in it and what is not.
* `planning/ToDos.md` — the search items, including the grouping question.
* `planning/decisions/0009-search-uses-the-model.md` — why there is no separate
  index, and what the per-rank buckets cost.
* `planning/decisions/0010-the-cursor-is-not-the-selection.md` — the keyboard
  model the results list has to stay inside.
* `planning/specs/CPACS_Documentation_System_Specification.md` — F12 to F14.
