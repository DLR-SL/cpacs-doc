# 0027 — The diagram is a second view of the tree

Date: 2026-09-30

## Context

The tree lists the instance tree for reading down. XSDDiagram, which CPACS
readers already know, draws the same structure left to right, compositors
included, and that picture is what many of them reach for first. The model has
everything the picture needs; the viewer had no way to draw it.

## Decision

- A second view at `/diagram/<path>/` (`#/diagram/<path>` in one file), the path
  meaning what it means under `/tree/`. The selection is shared between the
  views; what is expanded is each view's own.
- Drawn as hand-written SVG in `assets/diagram.js`, no library. Its structure
  comes from the types' member lists, where the compositors are; the tree
  nodes are claimed from there by line and name.
- In the diagram's view the grid has one column and the detail panel — the same
  element, rendered by the same code — is an overlay over the drawing's right
  edge. The strip keeps Tree and Diagram; Search and Handbook are the tree's.
- Laid out with XSDDiagram's Top alignment only; Center and Bottom are not
  offered, so every reader sees the same picture.
- Every element box names its type, and the name opens the type's
  documentation beside the drawing (a modified click opens the type page).

## Rationale

A second route rather than a toggle keeps an address for every picture, which
is what the tree's addresses were made for (D4). Hand-written SVG rather than a
layout library: the layout is a tidy tree, and
the line against libraries (N14) is the same one the viewer and the tests hold.
The overlay rather than the splitter: a diagram grows wide, and the column the
tree gives up is the width the drawing needs.

Not done here: links between the views from the panel and the type pages,
search inside the diagram, SVG export (F15, F16). The renderer draws into one
coordinate system, so export can follow without a second drawing path.

## Consequences

Every expand or collapse lays out and redraws the whole visible drawing, so its
cost grows with the number of visible boxes. Measured on the real CPACS 3.x
schema (2026-09-30, headless Chrome): about 30 ms typical, up to about 110 ms at
some 1,500 visible boxes, reached by expanding `wing` and three levels below it.
Accepted for now; viewport culling or incremental drawing is the known way out.

With an address that names a place, the documentation overlay opens over the
drawing's right edge and may cover that place's children until it is closed.
