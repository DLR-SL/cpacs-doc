# 0024 — The label outranks the route

Date: 2026-09-02

## Context

0023 renamed the borrowed block's opening line from `About the type <name>` to
`<name> documentation` and left the name as the link, expecting the wording to
stop readers clicking through to a panel that gives them less. It ended by
saying the fuller answer waited on whether the wording alone would do it. It
did not: the report came back that the line still invites the click and still
does not show that the documentation is right below it.

Measured on the real schema at `/cpacs/vehicles/aircraft/model/name`, dark
theme, against the page:

| | size | contrast | set |
| --- | --- | --- | --- |
| label (`documentation`) | 13.12 px | 8.1 : 1 | plain |
| link (`stringBaseType`) | 13.12 px | 9.4 : 1 | underlined, own hue, **first** |
| the prose it introduces | 19.04 px | 16.8 : 1 | — |

Two faults, and they are independent. The affordance outranked the label: the
link was the strongest thing on the line, the only underlined thing, in a hue
of its own, and it came first, so a scanning eye found one signal there and it
read "this way out". And the label did not own the block: at 31 % smaller than
the text below it, it has the proportions of a caption, so it read as something
hanging off the name rather than as the title of what follows.

Renaming addressed neither. It changed what the line says, and both faults are
in what the line *is*.

## Decision

- The name is plain text. Nothing in the label is a control.
- The route to the type stands after the label, in a `span.cd-borrowed-route`,
  and says where it leads: `show only the type`.
- The label is `--step-2` at weight 600, where it was `--step-0` at 400.
- A hairline runs the whole measure above the line, as the block's own
  `border-top`. It replaces the tick, which is removed.

## Rationale

**A section heading may not carry the link out of the section.** That is the
whole of the first fault. When the only control on a line is also the name of
what the reader is looking at, the control wins — no wording survives that.

**Rank by size and weight, not by loudness.** The label keeps `--ink-soft`, so
it is no louder than before; it is bigger and bolder, which is what makes a
heading. It stays under the tables' `h2` (`--step-3`, 600) so the borrowed
block does not outrank the sections around it, and under the prose, which is
what the reader came to read.

**The bar replaces the tick; it does not join it.** 0015 counted one stroke in
the reading part of this page and there is still one. Two marks for one
boundary would be two signs to learn, which is the objection 0015 raised
against marking both kinds of words.

A crossbar was declined twice before this, in 0015 and again in 0023, and both
refusals were about a *rail down the side of the block*, which fences the prose
and makes an aside of what is often the substance of the panel. A bar above the
line does not fence anything: it marks the join, which is what the reader was
not seeing. The stroke budget was the remaining objection, and swapping the two
settles it.

It takes `--rule`, where the tick took `--rule-strong`. Across a 44 rem measure
the bar is a multiple of the tick's length, and in the stronger ink it became
the loudest thing on the page.

**Above the line, not through it.** The request drew the label knocked out of
the middle of a rule. That wants the label painted in the page's own ground —
and the page paints none, the canvas being the UA's by `color-scheme`, so it
would mean introducing a background pair and keeping it in step across both
themes. A bar that merely fills what the label leaves was drawn and rejected on
sight: `transformationType documentation` and the route take most of the
measure between them, so what was left read as a stub rather than a boundary.

**The route keeps the link's colour and underline.** It is now the only control
on the line and has to look like one. Measured after the change it still holds
the higher ratio, 9.4 against the label's 8.1, and that is correct: what was
wrong was never that a link was visible, but that it was the largest, the
boldest and the first thing on a line whose job is to name what follows.

**`show only the type`, not `where else it is used`.** The type panel adds
three things — the derivation line, the citable page and the usage list — and a
link named after one of them would misdescribe the other two.

**`show only the type`, not `show type only`.** The shorter form was asked for
and reads in this viewer as a filter: the search takes `type:` and the `?`
strip glosses it `types only`. The article decides which of the two the reader
gets.

## Consequences

Measured in the same place after the change: the label is 16 px at weight 600
and is the first thing on the line, as plain `code`; the route is 13.12 px and
last; the prose is unchanged at 19.04 px.

`tests/test_viewer_provenance.py` gains
`test_the_label_outranks_the_route_that_used_to_outrank_it`, which asserts the
order the three sizes stand in rather than the sizes themselves. The two tests
that read the head read the label alone: what stands between the label and the
route on screen is the row's gap, which puts no character into `textContent`,
and the route is a button, so nothing runs together in the accessibility tree
either. `labelIsPlain` holds the part that matters most and is easiest to undo
by accident: no control inside the label. `mark` reads the block's
`border-top-width` where it read the tick's width.

A type absent from this schema is named and not routed, as `typeCell` already
had it.

This supersedes 0023, which was the same problem answered in words alone, and
0015 in the shape of the attribution line and in its mark. What 0015 settled
about *which* words are marked, about the mark opening the block rather than
fencing it — which the bar above the line still does — and about the tables
standing outside it, is untouched.

Still open, and now cheaper to reach: bringing those three things into the
borrowed block itself, which would leave the route with nothing to promise and
allow it to go. It is the answer that ends the question rather than balancing
it, and it waits on whether this one is enough.
