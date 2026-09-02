# 0023 — The line labels the block, it does not announce a topic

Date: 2026-09-02

## Context

0015 opened the borrowed block with `About the type <name>`, the name being the
link into the type. Readers report taking that line for a heading over a link
and clicking it to find out more.

What the click gives them is less, not more. `typeCell` swaps the panel rather
than following a link, so the tree and its selection stay put — but the type's
panel carries the same prose the node panel had just shown through
`appendBorrowedProse`, and the same tables, which the node panel already
appends through `appendTypeTables`. What it adds is three things: the
derivation line, the `citable page` link and the usage list. What it drops is
the element's head — occurrence, value type, constraints — and the element's
own words.

So a reader following that line trades the answer to "what is this place" for
three lines of metadata about the type, and 0015's own measurement says how
often the temptation stands there: 53,984 of 54,552 nodes carry a borrowed
block.

## Decision

The line reads `<name> documentation`, with the name still the link. It names
what stands below it instead of announcing a subject.

## Rationale

**"About X" promises somewhere else; "X documentation" points at the page.**
The misreading is not about weight or colour — the line is already muted and
already tick-marked. It is about grammar: a heading of the form "About X" is
what a link to an article is called, and the only interactive thing on the line
was X. Naming the block says the words are here, which removes the reason to
click without removing the ability to.

**Not a rule, and not a filled label.** Both were drawn (the request came with
a sketch of them). 0015 counted the strokes on the real panel of
`translation`: the tick is 1 of 50, the tables draw 48, and it is the only one
in the reading part of the page. A full-width rule adds a second stroke there
and re-opens the fence question 0015 settled by moving the mark from the side
of the block to its opening. A label on a filled ground reads as a button,
which is the reading being corrected.

**The name keeps the link.** It is the only route from a node to its type, and
the type panel does hold three things that exist nowhere else. Taking the link
away to stop a misreading would answer a wording fault with a lost route.

## Consequences

One line of the panel changes and nothing else does: the tick, the section, the
measure and the placement are 0015's and unaffected.

`tests/test_viewer_provenance.py` reads the new wording in the two tests that
assert the head, and carries the reason beside the first of them.

This supersedes 0015 in the wording of the attribution only. Everything else
0015 decided — what is marked and what is not, the mark opening rather than
fencing, the tables outside the block, the type named even where it has nothing
to lend — stands.

What it does not do is make the link's own reward legible. The alternative on
the table was to split the line: the name as plain text labelling the block,
and a separate short link at the end naming what the type panel adds. That is
the fuller answer and it adds furniture 0015 spent effort removing, so it waits
on whether the wording alone stops the clicks.
