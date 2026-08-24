# 0009 — Search is built from the model, not from a separate index

Date: 2026-08-24

## Context

§5 lists `search-index.json` as its own artefact, loaded lazily on first focus
of the search field. By the time the field can be focused, the viewer has the
model: 4.3 MB, 0.34 MB over the wire.

## Decision

The index is built in the browser from the loaded model, on the first
keystroke, and kept in memory. Nothing extra is shipped.

## Rationale

A second artefact would carry the same names, paths and summaries twice and
have to be regenerated in step with the model. The build already has one
consistency surface; a second one buys nothing here.

## Consequences

58,920 entries are scanned per query. Matches are collected into one bucket per
rank rather than sorted as a whole — a broad query matches tens of thousands of
entries to show sixty, and sorting all of them is where the time would go.
Measured 9–17 ms over the full set, against up to 45 ms when sorting
everything. If the schema grows by an order of magnitude, an inverted index
becomes the answer; at this size it would be premature.
