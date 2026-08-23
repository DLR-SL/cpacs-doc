# 0001 — Render ddue in Python, carry the HTML in the model

Date: 2026-08-23

## Context

The same type documentation appears in two places: on the static type pages, and
in the viewer's detail panel when navigating the tree. Something has to turn
`ddue` markup into HTML for both.

## Decision

The generator renders, in Python, once. The resulting fragments travel in the
model alongside the plain text, in `summaryHtml` and `remarksHtml`.

## Rationale

The alternative — keeping the model presentation-free and rendering in the
viewer — would need a second renderer in Python anyway, for the static pages.
Two implementations of a 25-element vocabulary drift apart, and the drift is
invisible until someone compares the two views side by side.

## Consequences

The model contains presentation. Text and HTML sit side by side rather than one
replacing the other, so search and diff still work on the text and a consumer
that wants neither can ignore both. The model grows by roughly 0.3 MB.
