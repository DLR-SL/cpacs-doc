# 0008 — The tree stays flat; choice membership is marked, not nested

Date: 2026-08-24

## Context

84 `choice` groups in the schema decide between alternatives, 48 of them
between groups of elements rather than single ones. The tree showed the
alternatives as ordinary siblings, which is wrong: only one of them may occur.

Compositor rows were tried first, mirroring the child table: a row for the
choice, its alternatives indented beneath.

## Decision

The tree lists every element at the depth of its instance path. Nodes belonging
to a choice carry a mark and an explanation on hover and focus. The
combinations are shown in the child table on the type page, which the mark
points to.

## Rationale

Indentation in a tree means containment in an instance, and a compositor
contains nothing — with group rows, `cylinderRadius` sat two levels below
`structure` although both are direct children of `vessel`. Group rows also
broke the expectation the rest of the tree sets up: everything else is
selectable and has an address, they were neither.

In the child table the same nesting is correct, because there indentation
describes the structure of a type rather than a path through a document.

## Consequences

2,848 nodes carry the mark. The tree no longer shows which alternatives belong
together — that is what the type page is for, and the mark says so.
