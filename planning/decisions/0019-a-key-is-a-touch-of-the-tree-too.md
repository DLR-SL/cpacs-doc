# 0019 — A key is a touch of the tree too

Date: 2026-09-02

## Context

0017 settled when the opening hint appears: at the reader's first click in the
tree, not at page load, and a tree key before that click calls it off for good.
The reasoning was that someone already driving with the keyboard has found the
keys by himself and would read the greeting as noise.

That reading holds for the line it was written against. It stopped holding at
0018, which put `Space` in the opening in Enter's place. A reader pressing an
arrow has found the guessable half — every tree he has used moves that way —
and has found nothing at all about the key that shows a detail page without
taking the keyboard out of the tree. The old rule therefore withheld the one
line he could not guess from the one reader who was certain never to see it
another way: he never clicks, so the click could never bring it.

## Decision

- The opening arrives at the reader's first touch of the tree, and a key is
  such a touch. The click keeps its listener; the key is taken where it is
  already seen, in the tree's own handler and in the global arrow handler.
- A key no longer calls the opening off, and no longer takes it away once it is
  out. Closing it is what marks it seen — the `×`, or Escape.

## Rationale

**A keypress is not proof that the hint is superfluous.** It was read as
proof, and it is evidence of the opposite: the reader is in the tree, on the
keys, and about to want the thing the hint's middle line names.

**Not at page load.** 0017's finding stands — standing there from the first
paint, the hint is furniture and is read as little as the rest of it. The
trigger is still the reader's first touch. Only what counts as a touch grew,
and it grew to the set that was always meant: a click is what everyone does,
which is why it was the trigger, not why it was the only one.

**The two hints now behave alike.** One asked for and one that came by itself
were taken away by different things, which needed `hintIsAutomatic` to tell
them apart. Both now stay until they are closed, and the state is gone with the
distinction.

## Consequences

`hintUsed()` is `hintStart()` and does the opposite of what it did.
`hintIsAutomatic` is removed.

A reader who neither closes the hint nor clicks the `×` sees it above the tree
on every page load, indefinitely. That is the cost of the decision and it is
deliberate: the alternative is guessing, from a keystroke, that he has read
it. It is one line, it carries its own close button, and Escape closes it.

Held in a browser: `test_the_hint_comes_out_for_a_reader_who_starts_on_the_keys`
covers both ways a key arrives — in the tree, and with the focus nowhere at all,
where the global handler takes the arrow into the tree.
`test_the_hint_stays_while_the_reader_uses_the_keys` holds the second half, and
`test_the_hint_can_be_put_away_by_hand_and_does_not_come_back` now carries the
"does not come back" that the old first-key test carried.

This supersedes 0017 in its second decision — when the opening appears and what
calls it off. The legend under the `?`, the placement above the tree and the
one-line width at the default tree width are unaffected.
