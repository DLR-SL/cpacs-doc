# 0004 — Tables get no header row

Date: 2026-08-23

## Context

`ddue:table` has no notion of a header row. Two of the thirteen tables in the
schema mark their first row with `legacyBold`; the other eleven do not.

## Decision

Every row renders as `<tr><td>`. No `<th>`, no `<thead>`.

## Rationale

Promoting the first row would be a guess about eleven tables in order to
accommodate two. Where the schema marks emphasis, the emphasis renders.

## Consequences

Tables lose the semantics a screen reader could use. If this matters, the fix is
in the schema — a convention for marking header rows — not in the renderer.
