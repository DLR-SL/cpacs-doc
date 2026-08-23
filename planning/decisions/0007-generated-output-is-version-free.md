# 0007 — Generated output carries no version and no deployment prefix

Date: 2026-08-23

## Context

§4.4 sketches URLs of the form `/v3.5.1/type/…`. The schema carries no
machine-readable version: the only occurrence in the file is prose inside a
documentation body. Separately, the router needs to know where it is deployed,
because it is served at arbitrary path depth.

## Decision

The generator produces documentation for whatever schema it is given, with no
version in the output and no prefix parameter. Type pages link relatively. The
router derives its prefix at run time by splitting the requested path at the
first `/tree/` segment.

## Rationale

Deployment decides where output goes — a directory on a website, as with the
existing Sandcastle chain. Parsing a version out of a documentation body would
be a guess. `tree` occurs nowhere as an element name in the instance tree, so
the split is unambiguous.

## Consequences

A version switcher (F17) cannot take its list from the model and needs a small
file maintained by the deployment. `xsd:schema/@version` is read where present
and recorded in `meta.schemaVersion`; its absence is a note in the build report.
