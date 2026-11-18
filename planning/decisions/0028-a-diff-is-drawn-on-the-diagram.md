# 0028 — A diff is drawn on the diagram

Date: 2026-11-18

## Context

Readers picture CPACS as the diagram. When the schema changes — a pull request, a
release, a project's own schema next to develop — they try to see the change in
that picture: which boxes are new, which are gone, where a type or a bound
changed. A text diff of the XSD answers none of that, and a type-by-type list
does not say where in the tree a change lands: a type used in twelve places
changes twelve places.

## Decision

- `cpacs-doc diff OLD NEW` builds both models with the same pipeline as `build`
  and compares them; it has its own arguments, because it takes two schemas.
- Types are compared by name; the instance trees are merged by path. Declaration
  ids are line numbers and are never used to match.
- One drawing with the changes on it, not two drawings side by side; *Before |
  After* is offered for a subtree, on aligned rows.
- The page is one self-contained file, written from its own template
  (`assets/diff.html`), not a mode of the viewer: it carries a different model
  (the merged tree) and is sent around, attached to a pull request, opened from
  a disk.
- The visual language of the viewer is kept: dashes say optional, magenta is the
  route. A status is never colour alone (+, −, ~, strike-through, the old value).
- Renames are guessed, and only a decision next to the new schema makes them
  certain; the decision travels with the schema it describes.

## Rationale

Matching on names and paths makes the comparison independent of formatting and
order in the file. Classifying every change for compatibility answers the first
question a reader of a change asks — does my file still validate? — and the
pairing of renames and moves keeps one edit from showing up as a removal and an
addition, which would overstate what breaks.

## Consequences

- The page duplicates the diagram's layout code instead of sharing
  `assets/diagram.js`; bringing the two together means teaching `diagram.js`
  a status per box.
- Without a decision file renames are only suspected, and moves of a renamed
  node need the rename confirmed first.
