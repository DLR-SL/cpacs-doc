# 0020 — Escape does the nearest thing first

Date: 2026-09-02

## Context

Escape has several claimants and one handler, which ran them in a fixed order:
the search panel, then the opening hint, then the tree. That order was written
when the hint was gone at the reader's first key, so a reader in the detail
panel practically never had one on screen. 0019 removed exactly that: the hint
now stands until it is closed, which makes it the normal state of a first-time
reader rather than a passing one.

Measured on the real schema, `ArrowDown`, `Enter`, `Escape`, `Escape`, reading
`document.activeElement` after each:

| | hint on screen | after Enter | after 1st Esc | after 2nd Esc |
| --- | --- | --- | --- | --- |
| first-time reader | yes | `cd-detail` | `cd-detail` | the cursor row |
| hint already closed | no | `cd-detail` | the cursor row | the cursor row |

So the first Escape out of the panel closed the hint and left the reader where
he stood — and what it closed was the strip that says `Esc back to the tree`.

## Decision

- Escape resolves by nearness, not by a fixed list: the search panel first;
  then, if the focus is anywhere inside the detail panel, back to the tree;
  then the hint; otherwise back to the tree.
- "Inside the panel" is the whole panel, not the panel element alone.
- Putting the Handbook away before asking for the cursor is one helper,
  `backToTree()`, shared by both branches that return.

## Rationale

**The nearer claimant wins.** A reader pressing Escape in the detail panel is
answering the question the panel put to him, not the one the strip above the
tree put to him five keystrokes earlier. Ordering by nearness is also the rule
that does not need revisiting when a fourth claimant appears: the search panel
was already ahead of the hint for the same reason.

**Not a second key.** Backspace was the alternative and would have worked: it
is unmapped in Chrome since 52 and in Firefox since 86, and the panel holds no
text field on the real schema — 0 across the 60 nodes walked above — so unlike
Enter and ArrowLeft it has no state in there where it already means something.
It was rejected because it is a synonym. The fault was never that Escape was
taken; it was that Escape was answered by the wrong claimant, and a second key
would have left that in place with a workaround on top of it.

**The whole panel.** 0018 settled that the way back may not depend on whether
the reader has tabbed on to a link, and this is the same rule seen from the
other side.

## Consequences

Escape closes the hint only from outside the detail panel. The `×` is
unchanged and closes it from anywhere, and the hint is one keystroke further
away for a reader who wanted it gone while reading a type page.

Held in a browser by `test_escape_leaves_the_panel_before_it_closes_the_hint`,
which starts from the state the table above measures — the hint up, the reader
in the panel — and asserts both halves: the first Escape returns to the row
Enter was pressed on and leaves the hint standing, the second closes it.

This does not reverse 0019. It is the consequence 0019 should have carried and
did not: making the hint persist changed which state Escape is pressed in most
often, and the order was written for the other one.
