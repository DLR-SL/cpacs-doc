# 0002 — A placeholder for the path back to the output root

Date: 2026-08-23

## Context

Rendered fragments contain image sources. The renderer cannot know how deep the
page consuming a fragment sits: type pages sit two levels below the output root,
the router is served at arbitrary depth, and the viewer inserts the same
fragment again.

## Decision

The renderer emits `%ROOT%` where the path back to the output root belongs.
Whoever writes the page substitutes it.

## Rationale

Absolute paths would tie the output to one deployment location, which is exactly
the property the output is supposed to keep. A build-time prefix parameter would
work but has to be supplied correctly every time, and getting it wrong produces
a site that looks fine locally and breaks once deployed.

## Consequences

Anything that emits rendered fragments must substitute the token. A test asserts
that no placeholder survives into written output.
