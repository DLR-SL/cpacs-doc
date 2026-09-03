# 0026 — The type is named, and the name is the link

Date: 2026-09-03

## Context

Three revisions of one line, each answering the report before it.

0015 opened the borrowed block with `About the type <name>`, the name being the
link. Readers took it for a heading over a link and clicked through. 0023
renamed it `<name> documentation` on the reading that "About X" promises
somewhere else while "X documentation" points at the page. They kept clicking.
0024 found why by measuring — the link was the largest, the only underlined and
the first thing on the line — took the link off the name, put the route after
it as `show only the type`, raised the label from `--step-0`/400 to
`--step-2`/600, and drew a bar across the measure above it.

The report now is the other failure, and it comes from the readers who know the
schema best: they run down a panel by its headings and pass this line over
without registering that the words below it belong to the type. `doorsType
documentation` puts the unknown word where the eye lands and the known one at
the end of the line, so what a scanning reader takes in is a name he does not
recognise.

Raising the line to `--step-3` — the size of `Attributes` and `Child elements`,
in `--ink-soft` — was tried and it works, and it is not what was missing. With
the name still plain text the line needed the size to be seen at all; a
signpost the eye recognises does the same job a step lower.

## Decision

- The line reads `Type: <name>`. The category word leads.
- The name is the link into the type panel again, written by `typeCell` as
  every other type name in the viewer is.
- `show only the type` and the `.cd-borrowed-route` it stood in are gone.
- The line is `--step-2` at weight 600. The word keeps `--ink-soft`; the name
  takes the link's hue and underline.

## Rationale

**The known word goes where the eye lands.** That is the whole of the first
change and it is independent of the second. A reader scanning a panel matches
what he already knows against what is on the screen, and `Type:` is what he is
looking for; a type name is what he is looking *at* once he has found it.
Neither `documentation` at the end of the line nor a step of size can do that
job, because the first is read last and the second only says "this is
important", not "this is what".

**The line no longer needs the name to label it, so the name is free to be a
link.** 0024's fault was precise: the only control on the line was also the
name of the block, so the line's affordance and its label were the same words,
and the affordance won. With `Type:` in front, the naming is done by the word.
`Type: doorsType` is a statement about this place, not an invitation to go
somewhere — and the prose it introduces begins directly under it, which is what
0023 wanted the wording to say.

**One way of writing a type name.** Every other type name on the panel is a
`typeCell`: underlined, in the link hue, and swapping the panel rather than
following a link. This was the one that was not, and a reader who has clicked
`stringBaseType` in the attribute table three rows above has already learnt
what a type name does here. Making this one inert taught him a second rule for
the same word.

**A link is a stronger mark than a step of size.** The hue and the underline
are the loudest thing this palette has, and nothing else on the line carries
them. Keeping `--step-3` on top of that made the borrowed block the loudest
thing on the panel and put it over the sections around it, which is what 0024
was right to avoid. At `--step-2` the line stays under `Attributes` and `Child
elements` in size and under the prose it introduces, and is found anyway.

**The click still costs what it cost.** The type panel drops the element's head
and its own words and adds three things (0023 counted them). Nothing here makes
that trade better; what changes is that the reader who takes it now means to.
The line says what it is before it says where it goes, and the route that was
there to make the trade explicit was itself the second thing on the line to
read.

## Consequences

Measured on `translation` in `fixtures/provenance.xsd` and on the real schema:
the line is 16 px at weight 600, the word in `--ink-soft` and the name in
`--link`, underlined; the section headings stay at 19.04 px and the prose at
19.04 px. The bar above the block, the block's margins and the placement of the
prose are 0024's and unaffected.

`tests/test_viewer_provenance.py` reads `Type: pointType` where it read
`pointType documentation`. `labelIsPlain` — no control inside the label — is
gone, being the thing this reverses; `kindIsPlain` takes its place and holds
what is still true, that the category word is not a control.
`test_the_label_outranks_the_route_that_used_to_outrank_it` and the size test
that followed it are replaced by two: the name carries the link's ink and the
word does not, and the line ranks under both the headings and the prose.

This supersedes 0024 in the name being plain text, in the route, and in the
label's size, and 0023 in the wording. What 0024 decided about the crossbar —
that it replaces the tick, runs the whole measure, and takes `--rule` — stands,
as does everything 0015 settled about which words are marked and about the
tables standing outside the block.

Open, and unchanged by this: bringing the derivation line, the citable page and
the usage list into the borrowed block, which would leave the link with nothing
the panel does not already have and let it go. 0024 left that question open and
it is still the answer that ends it rather than balancing it.
