# Design: Diagram view

Date: 2026-09-30
Status: draft, for review

A second view of the instance tree in the viewer, drawn the way XSDDiagram
draws it: boxes left to right, compositors as symbols, children expanded on
demand. Every element box names its type and links to that type's
documentation.

---

## 1. Intent

**Outcome.** A reader who knows XSDDiagram finds the same picture in the
browser, without installing anything, and reaches the type documentation from
any box in one click.

**Success criteria.**

- `/diagram/<path>/` opens the diagram with the ancestors of `<path>` expanded,
  the element at `<path>` selected and centered.
- Every element box shows name, cardinality (optional, repeated) and type; the
  type name opens the type documentation.
- The diagram is usable with the keyboard alone and with mouse zoom and pan.
- All three delivery forms work: `serve`, `build --site`, `build --single`.
- No new runtime or JavaScript dependency.

**In v1.** Diagram route, rendering and layout, documentation overlay, zoom and
pan, keyboard control, a minimal way in and out (a "Diagram" tab, a "Tree"
button).

**Not in v1.**

- Cross-links between the views: no "Show in diagram" / "Show in tree" in the
  detail panel or on type pages, and search does not jump into the diagram.
- Search and Handbook in diagram mode.
- Headless export from the command line (F16). The in-browser export (F15) is §4.9.
- Attributes in the diagram; they stay in the overlay's attribute table (F7).
- Viewport virtualisation.

---

## 2. Approach

Hand-written SVG in a new asset `diagram.js`, ES5, no library, next to
`viewer.js`. Rejected: HTML boxes with an SVG layer for the connectors (two
coordinate systems kept in step, harder zoom and export), and a layout library
such as ELK.js or d3-hierarchy (breaks the no-library line of N14 and the
one-file form, and a tidy left-to-right tree does not need one).

---

## 3. Routing and integration

### 3.1 Route

- `/diagram/<path>/` beside `/tree/<path>/`; `#/diagram/<path>` in the
  one-file form.
- `<path>` has the tree's semantics: instance path without the root element,
  resolved through the same `nodeByPath` map. It names the **selected** box.
- `parseLocation()` recognises the `/diagram/` segment as well and sets
  `state.view` to `"tree"` or `"diagram"`. Selecting a box pushes
  `/diagram/<path>/` through `history.pushState`.
- The URL scheme in §4.4 of the specification gains the line
  `/v3.5.1/diagram/vehicles/aircraft/model/ → resolved via 404.html`.

### 3.2 Server and generator

- `serve` already answers every path that is not a file with the router
  document. Diagram paths get the same treatment tree paths get: the address is
  kept, the status is 404 (the reasoning in `serve.py`).
- `ASSET_FILES` gains `diagram.js`. `router_html()` inlines it after
  `viewer.js` and adds `<div id="cd-diagram" class="cd-pane" hidden>`.
- The one-file form needs nothing beyond that: it inlines the assets already.

### 3.3 Layout of the window

- In diagram mode `#cd-app` carries `cd-app-diagram`. The grid has one
  column; the splitter is hidden. `#cd-diagram` is a fourth pane of the left
  column, beside tree, search and handbook, so the column's tab strip becomes
  the header over the full-width diagram.
- In diagram mode the strip shows only **"Tree"** (back to
  `/tree/<path>/`), **"Diagram"**, the theme button and `?`. "Search" and
  "Handbook" are hidden there.
- `#cd-detail` stays **the same element** and becomes an overlay: docked right,
  about 40 % wide (min 22 rem, max 48 rem), shadowed, with a close button. It
  is hidden until something is selected, and hidden again by the close button
  or Escape. `renderDetail()` runs unchanged, so type links, cross-references,
  "Used by", provenance and the handbook links all come along.

### 3.4 Way in

- The tree view's tab strip gains a **"Diagram"** tab. It opens
  `/diagram/<current path>/`. The selection (`state.path`) is shared, so the
  diagram opens where the tree was, and "Tree" returns to where the diagram was.

### 3.5 Module boundary

`diagram.js` is its own IIFE exposing one object:

```
CpacsDiagram.structure(model)            -> { root, children, elementChildren, find }
CpacsDiagram.layout(root, children, isOpen, measure) -> { boxes, width, height }
CpacsDiagram.mount(container, api)       -> { show(path), focus(), view() }
```

`structure` and `layout` are pure and tested on their own. `api` is what the
viewer lends `mount`: `model`, `select(path, focusDetail)`, `showType(name)`,
`typeRef(name)` (returns `null`, `{label}` or `{label, href}`) and
`gloss(compositor)`. The diagram knows nothing of URLs, the detail panel or
the tab strip; `viewer.js` changes only where it routes, switches the layout
class and mounts the diagram.

---

## 4. Rendering

### 4.0 Where the structure comes from

`model.tree` holds elements only; it has no nodes for compositors. The
compositor structure lives in the type's member list, `types[<type>].children`:
nested `group` (with `compositor`, bounds and `members`), `element` and `any`
entries, in document order, base content before extension content (0005).

The diagram therefore walks the member list of an element's type and claims,
for every `element` member, the child of the element's tree node whose
declaration has the same `line` and `name`. Groups and `any` have no tree node
and are built from the member alone.

An element is expandable when its tree node is not recursive and its type has
a non-empty member list — not when its tree node has children, since an
element whose content is only `xsd:any` has none and still has something to
show. Compositors have no expander of their own: they are always open, so
expanding an element shows its whole compositor structure down to the next
elements, as XSDDiagram does by default.

### 4.1 Shapes (after XSDDiagram)

| Item | Shape | Variants |
| --- | --- | --- |
| Element | Rectangle, name on the first line | `minOccurs=0`: dashed border. `maxOccurs>1`: a second rectangle offset (3, 3) behind it. |
| Type line | Second, smaller line in the element box: the type name as an SVG `<a>` with a real `href` | Labelled as the viewer's `typeLabel` does: an anonymous type with a base shows its base and links to the anonymous type; an anonymous type without a base has no type line. Built-in and unknown types are plain text. |
| `any` | Box like an element, dashed where optional, labelled `any` | Not selectable, not expandable. |
| Cardinality | Small text under the box, in the tables' notation (`0..1`, `1..∞`) | Omitted for `1..1`. |
| Compositor | Small octagon (corners bevelled by 30 % of the height) | `sequence`: line with three dots. `choice`: the switch symbol. `all`: the bracket symbol. Cardinality as for elements. `<title>` carries the `COMPOSITOR_GLOSS` text. |
| Expander | Small square with `+` / `−` at the right edge | Only on boxes with children. |
| Recursion | `↻` at the right edge instead of the expander | The node is not expandable, as in the tree. |
| Connector | Orthogonal: parent's right edge → vertical bus → each child's left edge | — |

The type line is an addition to XSDDiagram, and the point of the exercise: it
is the one-click route to the type documentation.

### 4.2 Layout

Recursive, over the **visible** subtree only, in two passes:

1. Bottom-up: a subtree's height is the sum of its children's subtree heights
   plus the gaps between them, and at least its own box height.
2. Top-down: a box stands at the top of its subtree — XSDDiagram's *Top*
   alignment, the only one offered (not *Center* or *Bottom*); a compositor
   that is its parent's only child is centered on the parent's box so the line
   runs straight. Children are stacked from the top.

x is per parent (amended 2026-09-30): the children of a box start 20 px past
that box, as in XSDDiagram, so siblings align and one long name widens only
its own branch. (The first version aligned every depth across the whole
drawing, which let a single long name stretch every branch.) Box width is the larger of name and type line, plus padding and
the expander. Text is measured once per string by a hidden `<text>` probe
(`getComputedTextLength()`), cached.

Compositors occupy a column of their own, as in XSDDiagram.

Every expand and collapse lays the visible subtree out again; what that costs
is measured in ADR 0027's Consequences. After the new layout the pan offset is corrected
so that the box that was expanded or collapsed stays where it was on screen.

### 4.3 Initial state

- Without a path: the root `cpacs` expanded one level, at 100 %, from the top
  left.
- With a path: ancestors expanded, target selected and centered, overlay open
  with the target's documentation.
- The set of expanded paths is the diagram's own. It is not shared with the
  tree, which keeps its own `state.expanded`.

### 4.4 Theme

Colours come only from CSS classes (`cd-dg-box`, `cd-dg-optional`,
`cd-dg-repeated`, `cd-dg-compositor`, `cd-dg-selected`, `cd-dg-cursor`, …)
using the existing variables (`--ink`, `--rule-strong`, `--plate`, `--link`,
`--focus`, …). No colour is written into the SVG, so dark mode and the theme
button work without code.

### 4.5 The route and the states (amended 2026-09-30)

- **The route.** The boxes and connector steps from the root to the selected
  element are drawn in `--trail` (magenta, the colour a navigation display
  gives the active route; used nowhere else in the viewer), 1.25 px at 70 % for the
  lines. The other connectors stay in `--rule-strong`. Hovering a box previews
  its route in the same colour at half strength. The path is there whenever
  a box is selected and goes with the selection (a click on the free canvas,
  §5.1); there is no separate switch for it.
- **One meaning per mark.** Dashes mean optional and nothing else. The
  selected element is a filled box (`--trail-fill`) with a `--trail` frame.
  The keyboard's place is a solid `--focus` ring around the box, shown only
  while the focus is in the drawing — unlike the tree, where the cursor mark
  stays visible (0016): in the drawing a second standing mark competed with
  the route.
- **The type line** is `--ink-soft` and turns into a visible link (`--link`,
  underlined) under the pointer or the keyboard; the element name carries
  weight 500.

---

## 5. Interaction

### 5.1 Mouse

- Click on a box: select it, highlight it, push the URL, open the overlay with
  the element's documentation.
- Click on the type name: `showType()`, the type documentation in the overlay.
  Ctrl-click and middle-click open the static type page, since the `href` is
  real (the same bargain `typeCell` makes).
- Click on `+` / `−`, or double-click on the box: expand or collapse, selection
  unchanged.
- A compositor is not selectable; it has no path. Its gloss shows on hover.
- A click on the free canvas clears the selection, as in XSDDiagram (amended
  2026-09-30): the mark and the path go, the overlay closes, and the address
  becomes the bare `/diagram/<root>/`. A click that ends a pan does not count.
  The bare address marks nothing; the root is marked once it is clicked.

### 5.2 Zoom and pan

- Drag on empty canvas pans. Wheel scrolls vertically, Shift+wheel
  horizontally, Ctrl+wheel zooms around the pointer.
- A small toolbar, bottom left: `−`, `+`, `100 %`, "Fit", "Center selection".
- Zoom range 25 %–200 %. The zoom level lasts for the page's lifetime; it is
  not in the URL.
- Implemented as one `transform` on the root `<g>`.

### 5.3 Keyboard

Follows 0010 and 0016–0021, adapted to two dimensions.

- A **cursor** apart from the selection (0010). The cursor box is the only tab
  stop; its focus ring is the cursor mark of 0016.
- `↑` / `↓`: previous / next sibling; past the end of the siblings, the nearest
  visible box of the same column above / below.
- `→`: expand; if already expanded, first child.
- `←`: collapse; if already collapsed, parent.
- The cursor visits elements only; compositors are passed over.
- `Home` / `End`: first / last box of the column.
- `Space`: select, overlay opens, keyboard stays in the diagram. `Enter`:
  select and move the keyboard into the overlay (0018).
- `Escape` and `Backspace` resolve by nearness (0020, 0021): out of the
  overlay back to the diagram; then close the overlay; then the hint.
- `+`, `−`, `0`: zoom in, out, to 100 %.
- A cursor that leaves the visible area pans the canvas along.
- ARIA: `role="tree"` on the SVG, `role="treeitem"` with `aria-level`,
  `aria-expanded`, `aria-selected` on the element boxes.
- The `?` table shows the diagram's keys while the diagram is showing.

---

## 6. Error handling

- A path that resolves to no node: the diagram shows the root expanded one
  level, and the overlay shows the same "Not found" the tree view shows; the
  server answers 404 as for tree paths.
- A type name with no entry in the model (built-in types, `xsd:*`): the type
  line is plain text, not a link, as `typeCell` does for built-ins.
- An empty model (no tree): the diagram pane says so in one line.

---

## 7. Tests

**Python, no browser**

- `router_html()` contains `#cd-diagram` and the inlined `diagram.js`;
  `ASSET_FILES` lists it; the one-file form carries it.
- `serve`: `/diagram/<valid path>/` answers the router document; the status is
  404 with the address kept, the same as `/tree/`.

**Browser, CDP (`tests/test_viewer_diagram.py`)**

- Rendering: root expanded; optional and repeated boxes carry their classes;
  compositors drawn as their symbols; a recursive node has no expander.
- Layout: no two boxes overlap (`getBBox()`); every box stands at the top of its
  subtree, and a lone compositor lines up with its parent; boxes of one depth share their x.
- Routing: `/diagram/a/b/` expands the ancestors, selects `b`, centers it;
  a click pushes the URL; the one-file form works on `#/diagram/…`.
- Overlay: selecting opens it with the element documentation; the type name
  shows the type documentation; its `href` is `/type/<name>/index.html`;
  closes with × and Escape.
- Keyboard: arrows move the cursor and expand / collapse; Space and Enter as
  0018; the cursor's focus ring is visible (the check 0011 introduced).
- Zoom and pan: Ctrl+wheel changes the scale around the pointer; "Fit" brings
  all boxes into view; an expanded box does not move on screen.
- Way in and out: "Diagram" tab opens the diagram at the selection, "Tree"
  returns to it.
- Theme: in dark mode box outline and text contrast against the canvas
  (computed style).

---

## 8. Documentation

- Decision `0027-the-diagram-is-a-second-view.md`: own route, shared
  selection, hand-written SVG, overlay rather than splitter.
- Specification: §3.3 names the diagram as a second layout; §4.4 gains the
  diagram route; §7.4 gains **F19 Diagram view** referring to this document,
  with F15 and F16 left as they are.
- README: one paragraph on `/diagram/` under `serve`.

### 4.6 Expert view (amended 2026-09-30)

A switch **Expert** in the diagram's toolbar, off by default, remembered per
browser (`localStorage`, key `cpacs-doc.diagramExpert`).

- **Off:** boxes carry the element name only, no type line. A bound is written
  only where the frame does not already say it: nothing for `1..1` (plain
  frame) and `0..1` (dashed frame); `1..∞`, `0..∞`, `2..4` and the like stay.
  The type documentation is reached through the overlay.
- **On:** every box carries its type line (§4.1) and every bound, `1..1`
  included.

Switching lays the drawing out again around the selected box, which keeps its
place on screen. The tree view is not affected.

### 4.7 Reading position, sheet, toolbar, motion (amended 2026-09-30)

- **An address that names a place** puts the chosen box where reading starts,
  not in the middle: its parent element whole at the left edge of what is
  visible (where that keeps the box in the left half; otherwise the box at
  30 % of the width), the box a sixth of the height from the top. Its subtree
  hangs below and to the right of it. The *Center* button still centers.
- **Narrow windows (≤ 48rem):** the documentation is a sheet along the bottom,
  58 % of the height, instead of a column over the right edge; the diagram
  keeps its boxes clear of whichever the overlay covers.
- **Tables in the overlay** read as lists: each row a run of labelled values,
  the first cell its heading, empty cells left out. The tree's panel keeps
  its tables. Tips inside the overlay take no room until shown.
- **Toolbar:** zoom out, the current scale (which resets to 100 %), zoom in
  as one joined control; then *Fit*, *Center*, and apart from them *Expert*.
- **Targets:** the expander's clickable area is 24 px square around its 10 px
  drawing.
- **Motion:** the boxes an expand brings in fade in from their parent's side
  in 140 ms; nothing else moves on its own, and with
  `prefers-reduced-motion: reduce` nothing moves at all.
- **Compositors** are drawn 36 × 18 with a symbol a little larger than
  XSDDiagram's, which at 100 % ran together into a dash, in `--ink-soft`
  with thin lines: they structure the drawing, the names are read.

### 4.8 Vertical rhythm (amended 2026-09-30)

Room under a box is kept only for what stands there — its bound (12 px) and
the stacked frame of a repeated item (3 px) — and sibling subtrees are 9 px
apart. A row without a bound thus takes 31 px instead of 45.

### 4.9 Export as an image (amended 2026-09-30)

Two joined buttons at the end of the toolbar, **PNG** and **SVG**, save the
drawing as it stands: what is expanded, the expert view, the path to the
selection and the theme's colours — independent of zoom and pan, so nothing
is cut off at the window's edge. The SVG carries its styles inline (the
page's custom properties do not travel with it) and none of the page's
machinery (focus rings, click areas, hover preview). The PNG is rendered at
twice the resolution, less where a very large drawing would pass what a
browser canvas holds; the SVG has no such limit. The file is named after the
root and the selected path, e.g. `cpacs-vehicles-aircraft.png`. Works in the
one-file form as well.
