# 0003 — Two hyphens encode the slash in anonymous type names

Date: 2026-08-23

## Context

Anonymous inline types are named after their owning element and therefore
contain a slash — `nacaProfileType/naca4DigitCode`. 97 of 1,206 catalogue
entries are affected. A slash cannot appear in a directory name.

## Decision

`/` becomes `--` in page paths.

## Rationale

Reversible, readable in a URL, and it occurs in no real type name — checked
against the whole catalogue, with no collisions and no case collisions either.
The alternative, giving anonymous types no page of their own and folding them
into their parent, would leave them without a citable address.

## Consequences

The encoding appears in citable URLs, so changing it later breaks links.
