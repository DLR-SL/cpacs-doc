# 0021 — Backspace is a second Escape

Date: 2026-09-02

## Context

0020 settled the order in which Escape resolves its claimants and rejected
Backspace in the same breath, on the ground that a synonym would paper over the
ordering fault rather than fix it. The ordering fault is fixed. What is left is
the plain ergonomic case that prompted the question: after Enter the hand is on
the right of the keyboard, and Backspace is where it already is.

The key is free. Chrome unmapped it from back-navigation in version 52 and
Firefox in version 86, both to stop accidental data loss in forms. Inside the
detail panel it collides with nothing: over 60 nodes walked on the real schema
the panel held 0 text fields — and a text field is the only thing that answers
the key — against 11 to 31 links, buttons and focusable terms per node, which
is what ruled Enter out.

## Decision

- Backspace answers wherever Escape answers, through the same resolution:
  search panel, detail panel, hint, tree. It is not a key of the panel's own.
- The search field keeps it. The text-field guard at the head of the global
  handler already does that and needs nothing added.
- The table behind the `?` names it beside Escape, as it names any pair.

## Rationale

**A synonym, or nothing.** Binding it only where it was asked for — the way out
of the panel — makes it the third key in three days that works in one state and
not the neighbouring one. 0018 removed ArrowLeft for that and 0020 declined
Backspace on the same reasoning. Sharing the whole resolution costs one clause
in one condition and leaves nothing to explain.

**Named, or it does not exist.** That is the finding of 0018 about Space, and
it applies to a key with no convention behind it at all: the APG assigns
Backspace nothing, so a reader has no reason to try it.

**`preventDefault` stays.** It already ran for Escape. It also covers the
reader who has put browser back-navigation back on the key by preference or
extension, for whom the page would otherwise leave under him.

## Consequences

The table's tree line is six entries and nine caps, and `Backspace` is the
longest cap in it. Measured with the table open, at the two ends of what the
splitter allows:

| tree column | hint box | sideways overflow | rows the line takes |
| --- | --- | --- | --- |
| 448 px (default) | 448 px | 0 | 3 |
| 200 px (`MIN_TREE_WIDTH`) | 200 px | 23 px | 6 |

The item `Esc Backspace back to the tree` is 214 px and carries
`white-space: nowrap`, so it is a floor the line cannot wrap below. At the
default width there is room; at the splitter's floor the box scrolls 23 px.
The word is kept anyway. `⌫` measures 0 overflow at 200 px, but it comes from
a system fallback rather than the code face — 20.5 px against that face's
8.8 px advance — so it is legible here and not dependably legible everywhere,
which is a poor trade for a state a reader reaches only by squeezing the
column to a third of its width.

Held in a browser by `test_backspace_is_a_second_escape`, which takes the panel
branch, and `test_backspace_is_left_to_the_search_field`, which asserts the
handler's part of the text-field case — the field keeps the focus and the
search stays open — and not the deletion, which is the browser's.

`tests/cdp.py` gained the key: the driver sends a real code and virtual key,
so a key it does not know cannot be pressed.

This supersedes 0020 in its "Not a second key" rationale only. The order Escape
resolves in is what 0020 settled and is unchanged — Backspace inherits it
whole, which is the point.
