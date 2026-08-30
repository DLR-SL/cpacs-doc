# 0014 — A table too wide for the column scrolls, the page does not

Date: 2026-08-30

## Context

A reference table is as wide as its widest name. The child table needs
1,143 px on `wingType`, 1,119 on `fuselageType` and 1,073 on `genericMassType`,
against 928 px of text column — the 58 rem measure less its padding. Measured
in a browser on the real schema at 1280 × 900, 1,079 of the 1,206 type pages
carry such a table.

Nothing held them, so the *page* took the overflow: at 1280 px `wingType` stood
46 px past the window, at 760 px it stood 478 px past it — and what slid out of
view first was the heading, the prose, the breadcrumb and the name column, the
one thing a reader needs while looking at a column on the right.

Code blocks never had the problem: they scroll in a container of their own
(`pre, .cd-code`, `overflow-x: auto`), which is the shape this decision copies.

## Decision

Every table the generator writes stands in a `div.cd-scroll` of its own —
attributes, child elements, allowed types, value constraints, allowed values,
and the declarations under "Used by". The container scrolls horizontally and
clips vertically, and a tip in the last row opens upwards instead of down.

## Rationale

The alternatives were measured rather than argued.

**Scrolling the section instead of the table** puts the heading inside the
scroller, which is the defect again one level in: the heading slides with the
first column.

**Making the table fit** is not possible without dropping what the table says.
`td code` is `nowrap` on purpose, since a wrapped type name is unreadable, and
the two columns that are empty on almost every page (`Constraints` on 92 % of
child tables, `Default` on 99 %) give back 45 to 105 px where the widest table
is 215 px over. That question stays open on its own merits; it is not a fix
for this one.

**`overflow-y` is `clip`, not the `auto` it would otherwise become.** A tip is
laid out even while hidden, so an `auto` container carries a vertical scrollbar
for an explanation nobody has opened. `overflow-clip-margin` is the declaration
that would leave the tips their room, and Chrome ignores it on a scroll
container — measured, not assumed.

**The clip therefore cuts a tip that opens past the last row**, and that is
where 20 of the 2,319 tips in tables stand, cut by up to 23 px and one of them
by 46. Those
open upwards, where the rows above leave 46 px at the least against the 41 a
tip and its gap take. Swept again over all 1,206 pages: none cut, and no page
wider than its window.

## Consequences

A wide table now has two scrollbars in the window — its own, and the page's for
the length of the page. That is the trade: the reader gives up one gesture that
moved everything at once and keeps the heading, the breadcrumb and the name
column in view while reading a column on the right.

Held in a browser by `tests/test_page_tables.py` on `fixtures/wide.xsd`, whose
names alone are wider than the column (0011): the page does not scroll, the
heading does not move while the table is scrolled to its end, and the tip on
the last row is drawn whole. Three of the four fail without the two rules; the
fourth states the premise.

The viewer's detail panel is not part of this. It has the same defect one level
down — the child table needs 1,110 px in a 718 px panel, so the panel scrolls
376 px sideways and the type's heading goes with it — and its tables are
written by `viewer.js`. The container and the rule are now there for it.

The tables `ddue` writes into prose are not part of it either, on measurement
rather than on principle: 6 stand on the documentation pages, none wider than
its column, and no type page is past the window.
