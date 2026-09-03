# 0025 — The panes divide the window

Date: 2026-09-03

## Context

0014 settled that a wide table scrolls and the page does not, and gave the
reason: the heading, the prose and the breadcrumb may not slide out of view
while a column on the right is being read. The viewer is that rule one level
out — two panes side by side, each with its own scrollbar, and a page that
stands still.

It was written as a constant. Both panes carried
`max-height: calc(100vh - 5rem)`, the 5rem standing for whatever chrome sits
above them, and nothing checked the guess against what is actually there. 0019
then made the keyboard hint come out on the reader's first key or click and
stay until it is closed. It is 65 px and a 0.9rem margin — 4.6 rem the guess
does not allow for.

Measured 2026-09-03 at 1500 × 950 on the real schema, Chrome and Firefox 155
alike:

| | on load | after the first key |
| --- | --- | --- |
| the hint | absent | 65 px |
| the column | 915 px | 984 px |
| the row it stands in | 915 px | 915 px |
| the document's own scroll | 0 | **69 px** |

What the reader meets is not a scrollbar. Enter hands the keyboard to the
detail panel (0018) and the arrows are the panel's, because a type page past
the fold is read with them. With 69 px of page under the layout, the first
arrow scrolled the *page* — the strip and the breadcrumb out of the window —
and the second reached the end of it, after which the key did nothing at all.
On a type whose panel has nothing of its own to scroll, that is the whole
effect of the key, and it was reported as the arrow keys not working in the
detail pane. It arrived as a Firefox report; Firefox is where it was seen, not
where it lives.

## Decision

- `.cd-app` states the height — `calc(100vh - 2.2rem)`, the window less the
  body's own padding — and stretches its items into it.
- `.cd-column` and `.cd-pane` carry `min-height: 0`, and the panes take
  `flex: 1 1 auto` where they took a `max-height`. Each pane scrolls inside
  what the row gives it.
- The one-column layout under 48rem resets both: there the page is the thing
  that scrolls, and the panes take their content's height.
- `#cd-tree` carries `tabindex="-1"`.

## Rationale

**A constant cannot know what stands above it.** The hint is the case that
broke it and not the only thing that could: the strip has taken a theme button
and a help button since it was written, and 0019 turned the hint from something
that goes away into something that stays. Any of those changes moves the number
and none of them is near the stylesheet. The layout can measure itself instead,
which is what a grid row with a stated height does.

**The window, not the viewport, and not `dvh`.** `100vh` less the body's
padding is exactly the box the app is given. `100dvh` would follow a mobile
browser's collapsing toolbar, which is a question for the one-column layout,
and that one does not use this height at all.

**`min-height: 0` is the whole of the flex part.** A flex item will not shrink
below its content unless it is told it may, so without it the tree would have
pushed the column past the row again and the fix would have been the same bug
in a different declaration.

**The tree pane is not a control.** Firefox 136 and later make a scroll
container with no tabindex of its own a keyboard tab stop. `#cd-tree` is one
and stands early in the document, so a single Tab out of the detail panel
landed on it, and the arrows 0018 gives the panel then moved the tree cursor
instead of scrolling what the reader was looking at — silently, since the panel
still looked like where he was. Chrome exempts a scroller that holds focusable
children and never did it. The rows are the tab stops here and keep their own
tabindex, so nothing becomes unreachable. This does not make the two browsers
agree: Firefox continues the tab sequence from the start of the document rather
than from a `tabindex="-1"` element, so Tab still leaves the panel, for the
strip instead of the tree. Fixing that needs focus management inside the panel,
which 0018 declined for its own reasons.

## Consequences

Measured again in the same place: the column is 915 px with the hint out, the
document has no scroll of its own, and the arrows scroll the panel and only the
panel. Where the panel has nothing to scroll they now do nothing, which is
correct and legible — before, the page moved 70 px first.

The detail panel is stretched to the row rather than sized to its content. It
paints no ground, so nothing about it looks different.

`tests/test_viewer_layout.py` holds it, on `fixtures/crowd.xsd`: the keyboard
tests run on a fixture whose tree is a dozen rows, where no arrangement of the
chrome can push the column past the window, so the module needs a schema with
70 elements under the root. Three tests, of which the first states the premise —
that the tree is long enough to fill its pane — so the other two cannot pass by
measuring nothing. Both fail against the old stylesheet, the second with the
70 px the reader was seeing.

Firefox cannot be driven by `tests/cdp.py`: Firefox 129 removed CDP and speaks
WebDriver BiDi. The reproduction was made with a throwaway BiDi driver over the
same `WebSocket` class; nothing of it is in the repository, and the regression
test runs where the rest of them do.

This extends 0014 rather than superseding it — the rule is the same rule, and
0014's containers on the type pages are untouched. It leaves 0018 and 0019
standing: the panel still claims no key of its own, and the hint still comes out
at the first touch of the tree and stays.
