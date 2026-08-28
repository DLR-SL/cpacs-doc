# 0011 — The viewer's keyboard behaviour is checked in a browser

Date: 2026-08-28

## Context

The viewer was checked two ways: the Python tests read the shell the generator
writes, and a DOM stand-in under Node exercised the logic. Both passed on the
first keyboard implementation, and it was unusable.

`.cd-node:focus { outline: none }` followed `.cd-node.cd-cursor { outline: … }`
with the same specificity, so the later rule won — on the row that always has
the focus, which is the cursor row. The arrow keys moved the cursor and nothing
was drawn. Expanding and collapsing were the only visible effects, and the
report was that the keys did nothing.

Verifying by hand had been the plan. It found the symptom and not the cause,
one round of manual testing per attempt.

## Decision

The keyboard behaviour is tested in a real browser. `tests/cdp.py` starts an
installed Chrome or Edge headless and speaks the DevTools protocol directly,
WebSocket framing included — no driver package, no Node. Twenty tests drive the
viewer over the development server, so the routing is the deployed one.

They skip where no such browser is found. CI sets `CPACS_DOC_REQUIRE_BROWSER`,
which turns the skip into a failure.

## Rationale

The defect class is invisible to everything else in the suite: it takes a
computed style, a real focus and a real key event. The test that covers it now
reads the outline off the cursor row — putting the rule back fails it, which is
how it was checked.

Against a driver package: a CDP session needs about a hundred lines of
WebSocket, and paying that once keeps the dependency list at `lxml` and the
test tooling at pytest (N14, E4). It is the same trade the viewer already makes
with no JavaScript library and the stylesheet with no framework.

Against keeping the Node stand-in: it was a second DOM implementation that had
to be believed, and everything it could check the browser checks better. It is
not part of the repository.

## Consequences

Twenty of the 116 tests need a browser. Both CI runner images carry Chrome;
`CPACS_DOC_BROWSER` points at one installed elsewhere. They take about one and
a half seconds together, with no fixed waits anywhere: CDP commands are
answered in order, so a key press is done when its answer arrives.

The protocol client is ours to keep working. It is used by the tests alone and
a CDP session asks little of it — text frames, one command at a time.

This reverses the call recorded in no earlier file, that a browser was not
worth the machinery. It was worth it after the first defect.
