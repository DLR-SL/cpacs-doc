# 0010 — The keyboard cursor is not the selection

Date: 2026-08-28

## Context

F1 asks for keyboard navigation modelled on XSDDiagram — arrow keys, Home and
End, Enter to focus the detail panel — and N13 for full keyboard operation with
ARIA roles for the tree. The tree had neither: every rendered row put two
buttons into the tab order, and no key was handled anywhere in it.

Two properties of the viewer decide what any answer can look like.
`renderTree()` clears the container and rebuilds it on every expansion and
every selection, so whatever holds the focus is destroyed. And a selection
writes a history entry, because the selected path is the URL.

## Decision

Three things, together:

- Arrow keys move a **cursor**, which is not the selection. Space selects and
  stays in the tree; Enter selects and hands the keyboard to the detail panel;
  Escape brings it back.
- Up and down move over the **visible rows**, not over siblings. Left and right
  collapse, expand, and step in and out of a node, as F1 describes.
- Every row is a `treeitem` carrying `aria-level`, `aria-posinset` and
  `aria-setsize`, and the cursor row is the tree's only tab stop. There are no
  nested `group` elements.

## Rationale

Selecting on every arrow key would push a history entry per keystroke and spend
the back button within a few rows. It would also leave F1's "Enter to focus the
detail panel" with nothing to do: Enter earns its place by being the key that
commits.

Up and down over visible rows departs from the literal wording of F1, which
says siblings. Siblings-only would mean the reader cannot leave a level with
the key that appears to do exactly that, and no tree anyone has used behaves
that way — not XSDDiagram's, not a file explorer's, not the WAI-ARIA tree
pattern that N13 invokes. F1 justifies itself with "the behaviour is already
learned", and this is the behaviour that is learned.

The flat ARIA form is the one the tree already has on screen (0008). Nesting a
`group` inside each `treeitem` is the alternative, and it makes the row's
accessible name its whole subtree unless the focusable element is split from
the labelled one. `aria-level` with `posinset` and `setsize` is what the
specification provides for exactly this shape.

Moving the cursor does not re-render. A step from one row to the next is two
attribute changes; rebuilding the tree for it is not something to do per
keystroke.

## Consequences

The cursor and the selection can be on different rows, so they are marked
differently — the selection keeps its background, the cursor takes an outline —
and both have to be visible at once. A rule that suppressed the outline on
focus made the cursor invisible on exactly the row that always has the focus,
which is why the browser tests of 0011 exist.

Where two rows share a path — 860 do, through the branches of a choice — the
cursor is recovered by path after a rebuild and the first row wins, as in
`indexTree()`.

The keys cannot be read off the tree, so they are said once in a strip above it
and stay reachable behind a `?` next to the search field. With nothing focused
at all, an arrow key would scroll a page that does not scroll — both panes
carry their own scrollbar — so it is taken into the tree instead.

Tab reaches the tree in at most two stops, the search field and the `?`, and
never one per row.
