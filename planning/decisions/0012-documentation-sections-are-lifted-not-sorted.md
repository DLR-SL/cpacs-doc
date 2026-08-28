# 0012 — The general documentation is lifted into sections, and not sorted

Date: 2026-08-28

## Context

The prose that describes CPACS as a whole hangs off `cpacsType`, the root
element's type, as `ddue:section` elements under one `remarks/content`. In
3.5.1 there are 31 of them, 5,720 words, every one titled and none nested:

- eleven numbered chapters, `1. Overview` to `11. Atmosphere` — 3,603 words,
  9 figures, 6 tables;
- twenty version entries, `CPACS 3.5.1` down to `CPACS 1.1` — 2,113 words;
- a two-row table of version and date, first in the body.

Rendered as one fragment, all of it could be read only by selecting the root
node and scrolling, or by opening `/type/cpacsType/`. The handbook of the
format was the least reachable page in its own documentation.

Eleven other types carry sections too, two to four apiece. There they are
headings inside a description, not chapters of a document.

## Decision

The sections of the root element's type are lifted out of its remarks and
become addressable: `documentation` in the model (version 1.1), a page each
under `/doc/<slug>/`, and a pane in the viewer that takes the tree's place
while it is open. The other eleven types are untouched.

The list is the document's own table of contents — document order, titles as
written. Nothing is grouped, sorted or classified.

Addresses are derived from the title mechanically, chapter number included.

## Rationale

Nothing but the text of a title distinguishes a chapter from a version entry.
Collapsing the twenty release notes into one menu item — which is what the
list wants, and what was proposed — takes a guess at a string: `^CPACS \d`,
or a leading number for a chapter. The day a heading reads `Version 4.0` the
guess stops matching, and it stops matching quietly: the entry simply appears
in the wrong place. That is the failure this project's first principle is
about, and it applies to the tool's own conveniences as much as to the schema's
defects.

The schema can say it instead. Wrapping the version entries in one section
titled `Release notes` makes the structure carry the meaning, and the menu
becomes twelve entries with no change here, because only top-level sections
are lifted.

Dropping the number from an address has the same shape: it would leave the tool
deciding which part of a heading means something, and let a renumbering pass
unnoticed by the URL.

The pane rather than a second navigation area: the search results already take
the tree's place in that slot, and a reader is never reading two of the three
at once. The tree itself was not an option — it shows instance paths (0008),
and a chapter has none.

## Consequences

`/type/cpacsType/` no longer carries the prose; it lists the chapters and links
to them. One copy, in one place, and the type page stops being a wall of text
that has nothing to do with attributes and children.

`serve` grew a `/doc/` route. The mode exists to reproduce the deployment
target, and the viewer offers these addresses as the citable ones.

A section without a title stays in the body and is reported: it has no name to
be listed under, and lifting it out would lose it. Two titles that resolve to
one address are reported and kept apart by a suffix.

Renumbering a chapter changes its address. That is the schema's decision to
make, and the report is where it becomes visible.
