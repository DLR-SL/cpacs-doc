# Diagram View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A second view of the instance tree in the viewer, `/diagram/<path>/`, drawn the way XSDDiagram draws it, with every element box linking to its type documentation.

**Architecture:** A new asset `diagram.js` (ES5 IIFE, no library) exports `CpacsDiagram.structure` (model → items, compositors included), `CpacsDiagram.layout` (pure left-to-right tidy tree) and `CpacsDiagram.mount` (SVG renderer with expand/collapse, zoom/pan, keyboard). `viewer.js` routes `/diagram/`, mounts the diagram into a fourth pane of the left column, switches the grid to one column and turns the existing detail panel into an overlay.

**Tech Stack:** Python 3.10+ / lxml (generator, dev server), plain ES5 JavaScript and CSS (viewer), pytest + the repository's own CDP driver `tests/cdp.py` against headless Chrome/Edge.

**Spec:** `planning/specs/2026-09-30-diagram-view-design.md`

## Global Constraints

- No new runtime or JavaScript dependency (N14): the viewer stays library-free, the test tooling stays pytest + `tests/cdp.py`.
- `diagram.js` is ES5 in the style of `viewer.js`: `var`, function declarations, `"use strict"`, comments explain why, not what.
- All three delivery forms must work: `serve`, `build --site`, `build --single` (fragment `#/diagram/<path>`).
- Colours only through CSS classes and the existing custom properties (`--page`, `--ink`, `--ink-soft`, `--rule-strong`, `--link`, `--focus`, `--field`); no colour literal in the SVG.
- Diagram paths are answered like tree paths: router document, address kept, HTTP 404.
- **Git:** the user commits and pushes. No `git add`, `git commit`, `git push` or branch operations in any task. Each task ends with the full test run instead.
- Run everything through uv: `uv run pytest …`.

## Review Focus

1. **Two elements with the same name under one parent** (a `choice` whose branches both hold `shared`, as in `minimal.xsd`): the path is the same for both; clicking the second must keep the second highlighted, and loading the URL selects the first — the tree's "first one found wins". Pinned in Task 5 (`test_twin_paths_select_the_box_that_was_clicked`, needs the viewer's `select → show` round trip).
2. **Measuring text in a pane that is not laid out** (mounting while hidden) returns 0 and would draw zero-width boxes. `textWidth` falls back to an estimate and does not cache it. Pinned in Task 4 (`test_boxes_have_room_for_their_names`).
3. **Real CPACS size**: fully expanding a large subtree must stay responsive. Checked in Task 8 against `D:\Entwicklung\Docs\CPACS\schema\cpacs_schema.xsd` (a measured timing, not a unit test).
4. **Browser Back/Forward across views** (`/tree/…` ↔ `/diagram/…`): the view must follow the address. Pinned in Task 5 (`test_back_returns_across_views`).
5. **Ctrl+wheel reaching the browser's own page zoom** when the handler is passive: the listener must be `{ passive: false }` and call `preventDefault`. Pinned in Task 6 (`test_ctrl_wheel_zooms_around_the_pointer` checks `devicePixelRatio` unchanged).

---

## File Structure

| File | Responsibility |
| --- | --- |
| `tests/fixtures/diagram.xsd` (create) | Fixture covering sequence, choice, all, any, optional, repeated, extension (two groups), recursion, anonymous type |
| `src/cpacs_doc/assets/diagram.js` (create) | Structure, layout, SVG rendering, zoom/pan, keyboard of the diagram |
| `src/cpacs_doc/assets/viewer.js` (modify) | Route `/diagram/`, view switch, overlay, tab, API for the diagram, Escape/hint integration |
| `src/cpacs_doc/assets/styles.css` (modify) | Diagram shapes, one-column grid, overlay, toolbar |
| `src/cpacs_doc/generator.py` (modify) | `ASSET_FILES`, `router_html()` (tab, pane, close button, inlined script) |
| `tests/cdp.py` (modify) | Keys `+ - 0`, `wheel()`, `drag()` |
| `tests/test_generator.py`, `tests/test_serve.py` (modify) | Shell and routing |
| `tests/test_viewer_diagram.py` (create) | `structure`, `layout`, `mount` in isolation |
| `tests/test_viewer_diagram_view.py` (create) | The view inside the viewer: routing, overlay, tabs, zoom/pan, keyboard, theme |
| `planning/decisions/0027-the-diagram-is-a-second-view.md` (create) | Decision record |
| `planning/specs/CPACS_Documentation_System_Specification.md`, `README.md` (modify) | F19, URL scheme, usage |

---

### Task 1: Fixture, asset and shell

**Files:**
- Create: `tests/fixtures/diagram.xsd`
- Create: `src/cpacs_doc/assets/diagram.js`
- Modify: `src/cpacs_doc/generator.py:968` (`ASSET_FILES`), `src/cpacs_doc/generator.py:981-1048` (`router_html`)
- Test: `tests/test_generator.py`, `tests/test_serve.py`

**Interfaces:**
- Produces: `window.CpacsDiagram` (empty object for now); DOM ids `cd-tab-diagram`, `cd-diagram`, `cd-overlay-close`; the fixture every later browser test uses.

- [ ] **Step 1: Write the fixture** `tests/fixtures/diagram.xsd`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- The diagram's fixture: every shape the diagram draws, once. A sequence,
     a choice and an all; an optional, a repeated and a recursive element; a
     type extending another (two groups, base first); an anonymous type
     without a base; content that is only xsd:any. -->
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:ddue="http://ddue.schemas.microsoft.com/authoring/2003/5"
            xmlns:sd="http://schemas.xsddoc.codeplex.com/schemaDoc/2009/3"
            elementFormDefault="qualified">

    <xsd:complexType name="baseType">
        <xsd:annotation>
            <xsd:appinfo>
                <sd:schemaDoc>
                    <ddue:summary><ddue:para>Base of everything.</ddue:para></ddue:summary>
                </sd:schemaDoc>
            </xsd:appinfo>
        </xsd:annotation>
        <xsd:sequence>
            <xsd:element name="uID" type="xsd:string"/>
        </xsd:sequence>
    </xsd:complexType>

    <xsd:complexType name="wingType">
        <xsd:annotation>
            <xsd:appinfo>
                <sd:schemaDoc>
                    <ddue:summary><ddue:para>A wing.</ddue:para></ddue:summary>
                </sd:schemaDoc>
            </xsd:appinfo>
        </xsd:annotation>
        <xsd:complexContent>
            <xsd:extension base="baseType">
                <xsd:sequence>
                    <xsd:element name="span" type="xsd:double" minOccurs="0"/>
                    <xsd:element name="sections" type="sectionsType" minOccurs="0"/>
                </xsd:sequence>
            </xsd:extension>
        </xsd:complexContent>
    </xsd:complexType>

    <xsd:complexType name="sectionsType">
        <xsd:sequence>
            <xsd:element name="section" type="sectionType" maxOccurs="unbounded"/>
        </xsd:sequence>
    </xsd:complexType>

    <xsd:complexType name="sectionType">
        <xsd:choice>
            <xsd:element name="profile" type="xsd:string"/>
            <xsd:element name="sections" type="sectionsType"/>
        </xsd:choice>
    </xsd:complexType>

    <xsd:complexType name="settingsType">
        <xsd:all>
            <xsd:element name="alpha" type="xsd:string" minOccurs="0"/>
            <xsd:element name="beta" type="xsd:string"/>
        </xsd:all>
    </xsd:complexType>

    <xsd:element name="cpacs">
        <xsd:complexType>
            <xsd:sequence>
                <xsd:element name="header" type="settingsType"/>
                <xsd:element name="wings" minOccurs="0">
                    <xsd:complexType>
                        <xsd:sequence>
                            <xsd:element name="wing" type="wingType" maxOccurs="unbounded"/>
                        </xsd:sequence>
                    </xsd:complexType>
                </xsd:element>
                <xsd:element name="extras" minOccurs="0">
                    <xsd:complexType>
                        <xsd:sequence>
                            <xsd:any minOccurs="0" processContents="lax"/>
                        </xsd:sequence>
                    </xsd:complexType>
                </xsd:element>
            </xsd:sequence>
        </xsd:complexType>
    </xsd:element>
</xsd:schema>
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_generator.py`:

```python
def test_the_router_carries_the_diagram():
    """The diagram is a fourth pane of the column, reached by a tab of its own,
    and its script stands before the viewer's, which mounts it."""
    html = generator.router_html()
    assert 'id="cd-tab-diagram"' in html
    assert 'id="cd-diagram"' in html
    assert 'id="cd-overlay-close"' in html
    assert html.index("window.CpacsDiagram") < html.index('var TREE_SEGMENT')


def test_the_diagram_script_is_an_asset(model, tmp_path):
    generator.generate(model, tmp_path)
    assert "diagram.js" in generator.ASSET_FILES
    assert (tmp_path / "assets" / "diagram.js").exists()


def test_the_one_file_form_carries_the_diagram(model):
    assert "window.CpacsDiagram" in generator.single_html(model)
```

Append to `tests/test_serve.py`:

```python
def test_a_diagram_path_answers_with_the_router_under_status_404(base):
    """The same bargain as a tree path: the address is kept, and the status
    says there is no file behind it."""
    status, body, headers = get(base, "/diagram/cpacs/wings/wing/")
    assert status == 404
    assert headers["Content-Type"].startswith("text/html")
    assert b'id="cd-diagram"' in body
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_generator.py tests/test_serve.py -q -k "diagram"`
Expected: 4 FAIL (`'id="cd-tab-diagram"' in html` false, `diagram.js` not in `ASSET_FILES`, …)

- [ ] **Step 4: Create** `src/cpacs_doc/assets/diagram.js`

```js
/* The instance tree, drawn the way XSDDiagram draws it
 * (planning/specs/2026-09-30-diagram-view-design.md).
 *
 * A second view of the model the tree shows: boxes left to right, the
 * compositors as symbols between them, children expanded on demand. The module
 * knows nothing of URLs, tabs or the detail panel; the viewer lends it what it
 * needs through `api` and hears back through `api.select` and `api.showType`.
 *
 * `structure` and `layout` are pure and exported, so the browser tests can hold
 * them to their contract without drawing anything.
 */
(function () {
  "use strict";

  window.CpacsDiagram = {};
})();
```

- [ ] **Step 5: Wire it into the generator**

In `src/cpacs_doc/generator.py` change line 968:

```python
ASSET_FILES = ("styles.css", "viewer.js", "diagram.js")
```

In `router_html()`:

1. After the Search tab button (the line ending `'...>Search'` … `'</button>'`), before `'<span class="cd-tabs-rest"></span>'`, add the tab. It stands last so the tree view's arrow order over Tree, Handbook, Search is unchanged:

```python
        # The diagram is a second view of the same tree, not a fourth place in
        # the column: in its view the column's own places step aside and the
        # strip keeps only the way back (spec 2026-09-30, §3.3).
        '<button id="cd-tab-diagram" class="cd-tab" type="button" role="tab"'
        ' aria-controls="cd-diagram" aria-selected="false" tabindex="-1">Diagram</button>'
```

2. After `'<div id="cd-docs" class="cd-pane" hidden></div>\n'` add:

```python
        # No tabindex of 0: the boxes are the tab stops, as the rows are in
        # the tree, and the SVG inside is the tree they belong to.
        '<div id="cd-diagram" class="cd-pane cd-diagram" tabindex="-1" hidden></div>\n'
```

3. After `'<div id="cd-detail" class="cd-pane cd-pane-detail" tabindex="-1"></div>\n'` add:

```python
        # Outside the panel, because the panel is emptied on every render.
        # Shown only while the panel is an overlay over the diagram.
        '<button id="cd-overlay-close" class="cd-overlay-close" type="button"'
        ' aria-label="Close the documentation">\u00D7</button>\n'
```

4. Replace `f"<script>\n{asset('viewer.js')}</script>\n"` with:

```python
        f"<script>\n{asset('diagram.js')}</script>\n"
        f"<script>\n{asset('viewer.js')}</script>\n"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_generator.py tests/test_serve.py -q -k "diagram"`
Expected: 4 passed

- [ ] **Step 7: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed (307 = 303 + 4). A failure in a tab test means the new tab changed the order; it must stand after Search.

---

### Task 2: `structure` — items from the model

**Files:**
- Modify: `src/cpacs_doc/assets/diagram.js`
- Create: `tests/test_viewer_diagram.py`

**Interfaces:**
- Produces: `CpacsDiagram.structure(model) -> { root, children(item), elementChildren(item), find(path) }`.
  Items are plain objects:
  - element: `{ key, kind: "element", node, name, type, min, max, path, selectable, recursive, expandable, members, children }`
  - group: `{ key, kind: "group", compositor, min, max, selectable: false, expandable: false, children }`
  - any: `{ key, kind: "any", name: "any", min, max, selectable: false, expandable: false, children: [] }`
  - `max` is `null` for unbounded. `key` is the root's `"0"` followed by `"." + index` per level, groups included; unique per item. `path` is the instance path without the root element (`[]` for the root). `find(path)` returns the chain `[root, …, target]` or `null`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_viewer_diagram.py`

```python
"""The diagram's parts, held to their contract one at a time.

`structure` and `layout` are pure: they take the model and give back items and
boxes, and nothing is drawn. `mount` draws, and is exercised here against a
host element and a stand-in for the viewer, so a failure points at the diagram
rather than at the view around it. The view inside the viewer is
`test_viewer_diagram_view.py`.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "diagram.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = (
    "return !!window.CpacsDiagram"
    " && document.querySelectorAll('[role=\"treeitem\"]').length > 1;"
)

# The model the viewer itself loads, fetched again so the pure functions can be
# called with it; `%s` is the body of a function of `model`.
WITH_MODEL = (
    "return fetch('/cpacs-doc-model.json')"
    ".then(function (r) { return r.json(); })"
    ".then(function (model) { %s });"
)


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the viewer")
    return browser


def run(page, body: str):
    return page.evaluate(WITH_MODEL % body)


# ---- structure ----

def test_the_root_is_the_root_element(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      return [s.root.kind, s.root.name, s.root.path.length, s.root.expandable, s.root.key];
    """) == ["element", "cpacs", 0, True, "0"]


def test_a_compositor_stands_between_an_element_and_its_children(page):
    """The tree has no node for a compositor; the type's member list has, and
    that is where the diagram takes it from (spec §4.0)."""
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      return s.children(s.root).map(function (k) {
        return [k.kind, k.compositor, k.children.map(function (c) { return c.name; })];
      });
    """) == [["group", "sequence", ["header", "wings", "extras"]]]


def test_all_and_choice_are_told_apart(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      var header = s.find(['header']).pop();
      var section = s.find(['wings', 'wing', 'sections', 'section']).pop();
      return [s.children(header)[0].compositor, s.children(section)[0].compositor];
    """) == ["all", "choice"]


def test_base_content_comes_before_extension_content(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      var wing = s.find(['wings', 'wing']).pop();
      return {
        max: wing.max,
        groups: s.children(wing).map(function (g) { return g.kind + ':' + g.compositor; }),
        elements: s.elementChildren(wing).map(function (e) { return e.path.join('/'); })
      };
    """) == {
        "max": None,
        "groups": ["group:sequence", "group:sequence"],
        "elements": ["wings/wing/uID", "wings/wing/span", "wings/wing/sections"],
    }


def test_bounds_are_carried(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      return [['header', 'alpha'], ['header', 'beta'], ['wings'], ['wings', 'wing', 'span']]
        .map(function (p) { var i = s.find(p).pop(); return [i.min, i.max]; });
    """) == [[0, 1], [1, 1], [0, 1], [0, 1]]


def test_a_recursive_element_is_not_expandable(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      var chain = s.find(['wings', 'wing', 'sections', 'section', 'sections']);
      var last = chain[chain.length - 1];
      return [chain.length, last.recursive, last.expandable, s.children(last).length];
    """) == [6, True, False, 0]


def test_an_element_holding_only_any_can_still_open(page):
    """`extras` has no child in the tree, and its type still has content to
    show: expandability is read off the members, not off the tree node."""
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      var extras = s.find(['extras']).pop();
      var sequence = s.children(extras)[0];
      return [extras.expandable, sequence.compositor,
              sequence.children.map(function (c) { return [c.kind, c.min, c.selectable]; })];
    """) == [True, "sequence", [["any", 0, False]]]


def test_an_unknown_path_is_not_found(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      return [s.find(['nope']), s.find(['wings', 'nope']), s.find([]).length];
    """) == [None, None, 1]


def test_keys_are_unique(page):
    assert run(page, """
      var s = CpacsDiagram.structure(model);
      var seen = {}, twice = [];
      (function walk(item) {
        if (seen[item.key]) twice.push(item.key);
        seen[item.key] = true;
        s.children(item).forEach(walk);
      })(s.root);
      return twice;
    """) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram.py -q`
Expected: 9 FAIL with `CpacsDiagram.structure is not a function`

- [ ] **Step 3: Implement** — in `diagram.js` replace the body of the IIFE (`window.CpacsDiagram = {};`) with:

```js
  function bound(value) {
    return value === undefined ? 1 : value;
  }

  /* ---- structure ----
   *
   * `model.tree` holds the elements and nothing else. The compositors are in
   * the member list of each element's type, so the diagram walks that list and
   * claims, for every element member, the tree child declared on the same line
   * under the same name. Groups and `any` have no tree node and are built from
   * the member alone.
   *
   * An element opens when its type has members, not when its tree node has
   * children: content that is only `xsd:any` has no tree child and still has
   * something to show. A recursive node does not open, as in the tree.
   */
  function structure(model) {
    var types = model.types || {};
    var declarations = model.declarations || {};

    function declarationOf(node) {
      return declarations[node.d] || {};
    }

    function membersOf(typeName) {
      var type = typeName ? types[typeName] : null;
      return type && type.children ? type.children : [];
    }

    function elementItem(node, decl, path, key) {
      var members = node && !node.recursive ? membersOf(decl.type) : [];
      return {
        key: key,
        kind: "element",
        node: node,
        name: decl.name || "?",
        type: decl.type || null,
        min: bound(decl.minOccurs),
        max: bound(decl.maxOccurs),
        path: path,
        // A member no tree node answers to has no path the viewer can show.
        selectable: !!node,
        recursive: !!(node && node.recursive),
        expandable: members.length > 0,
        members: members,
        children: null
      };
    }

    function claim(pool, member) {
      for (var i = 0; i < pool.length; i++) {
        var decl = declarationOf(pool[i]);
        if (decl.line === member.line && decl.name === member.name) {
          return pool.splice(i, 1)[0];
        }
      }
      return null;
    }

    function convert(members, owner, pool, prefix) {
      var out = [];
      for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var key = prefix + "." + i;
        if (member.kind === "group") {
          var group = {
            key: key,
            kind: "group",
            compositor: member.compositor,
            min: bound(member.minOccurs),
            max: bound(member.maxOccurs),
            selectable: false,
            expandable: false,
            children: null
          };
          group.children = convert(member.members || [], owner, pool, key);
          out.push(group);
        } else if (member.kind === "element") {
          var node = claim(pool, member);
          out.push(elementItem(
            node, node ? declarationOf(node) : member, owner.path.concat(member.name), key
          ));
        } else {
          out.push({
            key: key,
            kind: "any",
            name: "any",
            min: bound(member.minOccurs),
            max: bound(member.maxOccurs),
            selectable: false,
            expandable: false,
            children: []
          });
        }
      }
      return out;
    }

    // Built once per item and kept: the keys are positions, and they have to
    // mean the same box on every render.
    function children(item) {
      if (item.children) return item.children;
      if (item.kind !== "element" || !item.expandable) {
        item.children = [];
        return item.children;
      }
      var pool = (item.node.children || []).slice();
      item.children = convert(item.members, item, pool, item.key);
      return item.children;
    }

    // The elements an element contains, looking through its compositors.
    function elementChildren(item) {
      var out = [];
      (function walk(list) {
        for (var i = 0; i < list.length; i++) {
          if (list[i].kind === "group") walk(list[i].children);
          else if (list[i].kind === "element") out.push(list[i]);
        }
      })(children(item));
      return out;
    }

    // Where two elements share a path — the branches of a choice may — the
    // first one found wins, as it does in the tree's index.
    function find(path) {
      if (!root) return null;
      var chain = [root];
      var item = root;
      for (var i = 0; i < path.length; i++) {
        var candidates = elementChildren(item);
        var next = null;
        for (var j = 0; j < candidates.length; j++) {
          if (candidates[j].name === path[i]) {
            next = candidates[j];
            break;
          }
        }
        if (!next) return null;
        chain.push(next);
        item = next;
      }
      return chain;
    }

    var root = model.tree
      ? elementItem(model.tree, declarationOf(model.tree), [], "0")
      : null;
    return { root: root, children: children, elementChildren: elementChildren, find: find };
  }

  window.CpacsDiagram = {
    structure: structure
  };
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram.py -q`
Expected: 9 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed

---

### Task 3: `layout` — boxes from items

**Files:**
- Modify: `src/cpacs_doc/assets/diagram.js`
- Test: `tests/test_viewer_diagram.py`

**Interfaces:**
- Consumes: `structure(model)` from Task 2.
- Produces: `CpacsDiagram.layout(root, children, isOpen, measure) -> { boxes, width, height, columns }`.
  - `children(item) -> item[]`, `isOpen(item) -> bool`, `measure(item) -> { w, h }`.
  - Each box: `{ item, depth, parent, children, x, y, w, h, slot, span, inner }`; `boxes` in depth-first pre-order (parents before children, siblings top to bottom). `columns[d]` is the x of depth `d`.
  - Constants later tasks use: `CARD_ROOM = 12`, `STACK = 3`, `COLUMN_GAP = 30`, `ROW_GAP = 8`, `EXPANDER = 10`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_viewer_diagram.py`

```python
# ---- layout ----

# A fixed measure, so the geometry does not depend on the fonts installed.
LAYOUT = """
  var s = CpacsDiagram.structure(model);
  var measure = function (item) {
    return item.kind === 'group'
      ? { w: 34, h: 18 }
      : { w: 16 + item.name.length * 7, h: item.type ? 34 : 22 };
  };
  var isOpen = %s;
  var result = CpacsDiagram.layout(s.root, s.children, isOpen, measure);
  return {
    width: result.width,
    height: result.height,
    boxes: result.boxes.map(function (b) {
      return { key: b.item.key, name: b.item.name || b.item.compositor, depth: b.depth,
               x: b.x, y: b.y, w: b.w, h: b.h,
               children: b.children.map(function (c) { return c.item.key; }) };
    })
  };
"""

ALL_OPEN = "function (item) { return item.kind === 'group' || item.expandable; }"
ROOT_OPEN = "function (item) { return item.kind === 'group' || item.key === '0'; }"


def laid_out(page, is_open=ALL_OPEN) -> dict:
    return run(page, LAYOUT % is_open)


def test_a_closed_element_draws_no_children(page):
    names = [b["name"] for b in laid_out(page, ROOT_OPEN)["boxes"]]
    assert names == ["cpacs", "sequence", "header", "wings", "extras"]


def test_no_two_boxes_overlap(page):
    boxes = laid_out(page)["boxes"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            apart = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
                     or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
            assert apart, f"{a['name']} overlaps {b['name']}"


def test_a_parent_is_centred_on_its_children(page):
    boxes = laid_out(page)["boxes"]
    by_key = {b["key"]: b for b in boxes}
    for box in boxes:
        if not box["children"]:
            continue
        first, last = by_key[box["children"][0]], by_key[box["children"][-1]]
        middle = (first["y"] + first["h"] / 2 + last["y"] + last["h"] / 2) / 2
        assert abs(box["y"] + box["h"] / 2 - middle) < 0.5, box["name"]


def test_a_depth_is_a_column(page):
    """Boxes of one depth share their x, and a column starts past the widest
    box of the one before it."""
    boxes = laid_out(page)["boxes"]
    xs, widest = {}, {}
    for box in boxes:
        xs.setdefault(box["depth"], set()).add(box["x"])
        widest[box["depth"]] = max(widest.get(box["depth"], 0), box["w"])
    assert all(len(v) == 1 for v in xs.values())
    for depth in range(1, len(xs)):
        assert min(xs[depth]) >= min(xs[depth - 1]) + widest[depth - 1] + 1


def test_the_drawing_holds_every_box(page):
    result = laid_out(page)
    for box in result["boxes"]:
        assert box["x"] >= 0 and box["y"] >= 0
        assert box["x"] + box["w"] <= result["width"]
        assert box["y"] + box["h"] <= result["height"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram.py -q -k "layout or column or overlap or centred or closed or holds"`
Expected: 5 FAIL with `CpacsDiagram.layout is not a function`

- [ ] **Step 3: Implement** — in `diagram.js`, directly after `"use strict";` add the geometry:

```js
  // Geometry, in diagram units: pixels at 100 %.
  var PAD_X = 8;           // text inset inside a box
  var LINE_ONE = 22;       // a box holding the name alone
  var LINE_TWO = 34;       // a box holding the name and the type under it
  var GROUP_W = 34;
  var GROUP_H = 18;
  var EXPANDER = 10;       // side of the +/- square, centred on the right edge
  var STACK = 3;           // offset of the second frame behind a repeated item
  var CARD_ROOM = 12;      // room under a box for its cardinality
  var COLUMN_GAP = 30;     // from the widest box of a column to the next column
  var ROW_GAP = 8;         // between sibling subtrees
  var MARGIN = 24;         // between the drawing and the edge of the pane
  var ZOOM_MIN = 0.25;
  var ZOOM_MAX = 2;
```

and after `structure` (before `window.CpacsDiagram = …`):

```js
  /* ---- layout ----
   *
   * XSDDiagram's tidy tree, over the visible items only. Bottom up, a subtree
   * is as tall as its children together, and at least as tall as its own box;
   * top down, a box is centred on its children. A depth is a column as wide as
   * its widest box, so boxes of one depth line up — calmer than XSDDiagram's
   * per-box indent, and the column is what the keyboard moves along.
   */
  function layout(root, children, isOpen, measure) {
    var boxes = [];
    var widths = [];

    function collect(item, depth, parent) {
      var size = measure(item);
      var box = {
        item: item, depth: depth, parent: parent, children: [],
        x: 0, y: 0, w: size.w, h: size.h,
        slot: size.h + CARD_ROOM + STACK, span: 0, inner: 0
      };
      boxes.push(box);
      widths[depth] = Math.max(widths[depth] || 0, size.w);
      if (isOpen(item)) {
        var list = children(item);
        for (var i = 0; i < list.length; i++) {
          box.children.push(collect(list[i], depth + 1, box));
        }
      }
      return box;
    }

    function measureSpan(box) {
      var sum = 0;
      for (var i = 0; i < box.children.length; i++) {
        sum += measureSpan(box.children[i]) + (i ? ROW_GAP : 0);
      }
      box.inner = sum;
      box.span = Math.max(box.slot, sum);
      return box.span;
    }

    function place(box, top, columns) {
      box.x = columns[box.depth];
      if (!box.children.length) {
        box.y = top + (box.span - box.slot) / 2;
        return;
      }
      var cursor = top + (box.span - box.inner) / 2;
      for (var i = 0; i < box.children.length; i++) {
        place(box.children[i], cursor, columns);
        cursor += box.children[i].span + ROW_GAP;
      }
      var first = box.children[0];
      var last = box.children[box.children.length - 1];
      var middle = (first.y + first.h / 2 + last.y + last.h / 2) / 2;
      box.y = middle - box.h / 2;
    }

    if (!root) return { boxes: [], width: 0, height: 0, columns: [] };
    var top = collect(root, 0, null);
    var columns = [0];
    for (var d = 0; d < widths.length; d++) {
      columns[d + 1] = columns[d] + widths[d] + COLUMN_GAP;
    }
    measureSpan(top);
    place(top, 0, columns);

    // Centring a tall parent on short children can lift it above the top.
    var least = 0;
    var height = 0;
    for (var i = 0; i < boxes.length; i++) least = Math.min(least, boxes[i].y);
    for (var j = 0; j < boxes.length; j++) {
      boxes[j].y -= least;
      height = Math.max(height, boxes[j].y + boxes[j].slot);
    }
    var last = widths.length - 1;
    return {
      boxes: boxes,
      width: columns[last] + widths[last] + STACK + EXPANDER,
      height: height,
      columns: columns
    };
  }
```

Change the export to:

```js
  window.CpacsDiagram = {
    structure: structure,
    layout: layout
  };
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram.py -q`
Expected: 14 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed

---

### Task 4: `mount` — drawing, expanding, choosing

**Files:**
- Modify: `src/cpacs_doc/assets/diagram.js`
- Modify: `src/cpacs_doc/assets/styles.css` (append a diagram block at the end)
- Test: `tests/test_viewer_diagram.py`

**Interfaces:**
- Consumes: `structure`, `layout`.
- Produces: `CpacsDiagram.mount(container, api) -> { show(path, centre), focus(), view() }`
  - `api = { model, select(path, focusDetail), showType(typeName), typeRef(typeName), gloss(compositor), covered() }`; `typeRef` returns `null` (no type line), `{ label, link: false }` (plain text) or `{ label, link: true, href? }`; `covered()` is the width in px the viewer lays over the right edge of the pane (the open overlay), `0` otherwise.
  - `show(path, centre) -> bool`: opens the ancestors, selects the item at `path`, draws; with `centre` true it centres the item, otherwise it only pans when the item is out of view. Returns `false` (and draws the root) when the path is unknown.
  - `focus()`: puts the keyboard on the cursor box. `view() -> { scale, x, y }`.
  - DOM contract the view tests rely on: `svg.cd-dg-svg[role=tree]` > `g.cd-dg-view[transform]` > `g.cd-dg-links` (`path.cd-dg-link`) and `g.cd-dg-items` (`g.cd-dg-item.cd-dg-element|cd-dg-group|cd-dg-any[data-key]`); element items carry `data-path`, `role=treeitem`, `aria-level`, `aria-selected`, `aria-expanded` (if expandable), `tabindex`; children `rect.cd-dg-frame`, `rect.cd-dg-shadow` (repeated), `rect.cd-dg-ring`, `text.cd-dg-name`, `a.cd-dg-type[data-type]` > `text.cd-dg-type-text` (or a bare `text.cd-dg-type-text`), `g.cd-dg-expander`, `text.cd-dg-recursive`, `text.cd-dg-card`. Classes `cd-dg-optional`, `cd-dg-repeated`, `cd-dg-selected`, `cd-dg-cursor`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_viewer_diagram.py`

```python
# ---- mount ----

# The diagram in a host of its own, over the page, with a stand-in for the
# viewer that records what the diagram asks of it.
MOUNT = """
  var host = document.getElementById('dg-host');
  if (host) host.remove();
  host = document.createElement('div');
  host.id = 'dg-host';
  host.style.cssText = 'position:fixed;left:0;top:0;width:1200px;height:800px;'
    + 'z-index:50;background:var(--page)';
  document.body.appendChild(host);
  window.dgCalls = [];
  window.dg = CpacsDiagram.mount(host, {
    model: model,
    select: function (path, focus) { dgCalls.push(['select', path.join('/'), !!focus]); },
    showType: function (name) { dgCalls.push(['type', name]); },
    typeRef: function (name) {
      if (!name) return null;
      var type = model.types[name];
      if (!type) return { label: name, link: false };
      if (type.anonymous && !type.base) return null;
      return { label: name, link: true, href: '/type/' + name + '/index.html' };
    },
    gloss: function (name) { return 'gloss ' + name; },
    covered: function () { return 0; }
  });
  return true;
"""

HELPERS = """
  window.dgItem = function (path) {
    return document.querySelector('#dg-host .cd-dg-item[data-path="' + path + '"]');
  };
  window.dgHit = function (node) {
    node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
  };
  return true;
"""


@pytest.fixture
def mounted(page):
    run(page, MOUNT)
    page.evaluate(HELPERS)
    return page


def names(page):
    return page.evaluate("""
      return Array.prototype.map.call(
        document.querySelectorAll('#dg-host .cd-dg-element .cd-dg-name'),
        function (t) { return t.textContent; });
    """)


def test_the_root_opens_one_level(mounted):
    assert names(mounted) == ["cpacs", "header", "wings", "extras"]
    assert mounted.evaluate("""
      return [dgItem('').getAttribute('aria-expanded'),
              dgItem('header').getAttribute('aria-expanded')];
    """) == ["true", "false"]


def test_optional_is_dashed_and_repeated_is_stacked(mounted):
    result = mounted.evaluate("""
      dg.show(['wings', 'wing'], false);
      var wings = dgItem('wings'), wing = dgItem('wings/wing'), header = dgItem('header');
      return {
        wingsOptional: wings.classList.contains('cd-dg-optional'),
        dash: getComputedStyle(wings.querySelector('.cd-dg-frame')).strokeDasharray,
        headerDash: getComputedStyle(header.querySelector('.cd-dg-frame')).strokeDasharray,
        repeated: wing.classList.contains('cd-dg-repeated'),
        shadow: !!wing.querySelector('.cd-dg-shadow'),
        card: (wing.querySelector('.cd-dg-card') || {}).textContent,
        headerCard: !!header.querySelector('.cd-dg-card')
      };
    """)
    assert result["wingsOptional"] and result["dash"] != "none"
    assert result["headerDash"] == "none"
    assert result["repeated"] and result["shadow"]
    assert result["card"] == "1..\u221e"
    assert result["headerCard"] is False


def test_compositors_are_drawn_as_symbols(mounted):
    result = mounted.evaluate("""
      dgHit(dgItem('header').querySelector('.cd-dg-expander'));
      var all = document.querySelector('#dg-host .cd-dg-group[data-compositor="all"]');
      return all ? [all.querySelector('title').textContent,
                    all.querySelectorAll('.cd-dg-symbol-dot').length,
                    !!all.querySelector('.cd-dg-expander')] : null;
    """)
    assert result == ["gloss all", 3, False]


def test_a_recursive_element_has_no_expander(mounted):
    assert mounted.evaluate("""
      dg.show(['wings', 'wing', 'sections', 'section', 'sections'], false);
      var item = dgItem('wings/wing/sections/section/sections');
      return [!!item.querySelector('.cd-dg-recursive'), !!item.querySelector('.cd-dg-expander'),
              item.hasAttribute('aria-expanded')];
    """) == [True, False, False]


def test_the_type_line_links_to_the_type(mounted):
    result = mounted.evaluate("""
      dg.show(['wings', 'wing', 'uID'], false);
      var header = dgItem('header').querySelector('a.cd-dg-type');
      var uid = dgItem('wings/wing/uID').querySelector('.cd-dg-type-text');
      return {
        href: header && header.getAttribute('href'),
        uidText: uid.textContent,
        uidLinked: !!uid.closest('a'),
        wingsLine: !!dgItem('wings').querySelector('.cd-dg-type-text')
      };
    """)
    assert result == {
        "href": "/type/settingsType/index.html",
        "uidText": "xsd:string",
        "uidLinked": False,
        "wingsLine": False,
    }


def test_a_click_on_the_type_selects_and_shows_the_type(mounted):
    assert mounted.evaluate("""
      var before = location.href;
      dgHit(dgItem('header').querySelector('.cd-dg-type-text'));
      return [dgCalls, location.href === before];
    """) == [[["select", "header", False], ["type", "settingsType"]], True]


def test_a_click_on_a_box_selects_it(mounted):
    assert mounted.evaluate("""
      dgHit(dgItem('header').querySelector('.cd-dg-frame'));
      var header = dgItem('header');
      return [dgCalls, header.classList.contains('cd-dg-selected'),
              header.getAttribute('aria-selected')];
    """) == [[["select", "header", False]], True, "true"]


def test_the_expander_opens_without_selecting(mounted):
    assert mounted.evaluate("""
      dgHit(dgItem('wings').querySelector('.cd-dg-expander'));
      return [dgCalls.length, dgItem('wings').getAttribute('aria-expanded'), !!dgItem('wings/wing')];
    """) == [0, "true", True]


def test_an_expanded_box_stays_where_it_was(mounted):
    moved = mounted.evaluate("""
      var before = dgItem('wings').querySelector('.cd-dg-frame').getBoundingClientRect();
      dgHit(dgItem('wings').querySelector('.cd-dg-expander'));
      var after = dgItem('wings').querySelector('.cd-dg-frame').getBoundingClientRect();
      return [after.left - before.left, after.top - before.top];
    """)
    assert abs(moved[0]) < 0.5 and abs(moved[1]) < 0.5


def test_connectors_join_parent_and_children(mounted):
    assert mounted.evaluate(
        "return document.querySelector('#dg-host .cd-dg-link').getAttribute('d').length > 0;"
    )


def test_boxes_have_room_for_their_names(mounted):
    """Measured text, not an estimate: every name ends inside its frame."""
    assert mounted.evaluate("""
      var bad = [];
      document.querySelectorAll('#dg-host .cd-dg-element').forEach(function (g) {
        var frame = g.querySelector('.cd-dg-frame').getBBox();
        var name = g.querySelector('.cd-dg-name').getBBox();
        if (name.x + name.width > frame.x + frame.width) bad.push(g.getAttribute('data-path'));
      });
      return bad;
    """) == []


def test_a_show_for_the_clicked_path_keeps_the_mark(mounted):
    """The viewer answers every click with `show` for the same path; that must
    not move the mark or the view."""
    assert mounted.evaluate("""
      dgHit(dgItem('wings').querySelector('.cd-dg-frame'));
      var before = dg.view();
      dg.show(['wings'], false);
      var after = dg.view();
      return [dgItem('wings').classList.contains('cd-dg-selected'),
              before.x === after.x && before.y === after.y];
    """) == [True, True]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram.py -q`
Expected: the 12 new mount tests FAIL with `CpacsDiagram.mount is not a function`; the 14 earlier tests pass

- [ ] **Step 3: Implement drawing** — in `diagram.js`, after `layout`, add:

```js
  /* ---- drawing ---- */

  var SVG_NS = "http://www.w3.org/2000/svg";

  function svg(tag, attributes, parent) {
    var node = document.createElementNS(SVG_NS, tag);
    for (var name in attributes) {
      if (Object.prototype.hasOwnProperty.call(attributes, name)) {
        node.setAttribute(name, attributes[name]);
      }
    }
    if (parent) parent.appendChild(node);
    return node;
  }

  // The bounds as XSDDiagram writes them under a box. Nothing for 1..1, which
  // an unmarked box already says.
  function cardinality(item) {
    if (item.min === 1 && item.max === 1) return "";
    return item.min + ".." + (item.max === null ? "\u221E" : item.max);
  }

  function isRepeated(item) {
    return item.max === null || item.max > 1;
  }

  // XSDDiagram's compositor box: a rectangle with its corners bevelled by
  // 30 % of its height.
  function octagon(x, y, w, h) {
    var b = Math.round(h * 0.3);
    return "M" + (x + b) + " " + y + "H" + (x + w - b)
      + "L" + (x + w) + " " + (y + b) + "V" + (y + h - b)
      + "L" + (x + w - b) + " " + (y + h) + "H" + (x + b)
      + "L" + x + " " + (y + h - b) + "V" + (y + b) + "Z";
  }

  // The three symbols, after XSDDiagram's own: a line with three beads for a
  // sequence, a switch for a choice, brackets for all.
  function drawSymbol(parent, compositor, cx, cy) {
    var d;
    var dots;
    if (compositor === "sequence") {
      d = "M" + (cx - 12) + " " + cy + "H" + (cx + 12);
      dots = [[cx - 5, cy], [cx, cy], [cx + 5, cy]];
    } else if (compositor === "choice") {
      d = "M" + (cx - 12) + " " + cy + "H" + (cx - 8) + "L" + (cx - 4) + " " + (cy - 4)
        + "M" + (cx + 4) + " " + (cy - 4) + "H" + (cx + 8)
        + "M" + (cx + 4) + " " + cy + "H" + (cx + 12)
        + "M" + (cx + 4) + " " + (cy + 4) + "H" + (cx + 8)
        + "M" + (cx + 8) + " " + (cy - 4) + "V" + (cy + 4);
      dots = [[cx, cy - 4], [cx, cy], [cx, cy + 4]];
    } else {
      d = "M" + (cx - 4) + " " + (cy - 4) + "H" + (cx - 8) + "V" + (cy + 4) + "H" + (cx - 4)
        + "M" + (cx - 12) + " " + cy + "H" + (cx - 8)
        + "M" + (cx + 4) + " " + (cy - 4) + "H" + (cx + 8) + "V" + (cy + 4) + "H" + (cx + 4)
        + "M" + (cx + 8) + " " + cy + "H" + (cx + 12);
      dots = [[cx, cy - 4], [cx, cy], [cx, cy + 4]];
    }
    svg("path", { "class": "cd-dg-symbol-line", d: d }, parent);
    for (var i = 0; i < dots.length; i++) {
      svg("circle", { "class": "cd-dg-symbol-dot", cx: dots[i][0], cy: dots[i][1], r: 1.6 }, parent);
    }
  }

  function drawExpander(parent, cx, cy, open) {
    var group = svg("g", { "class": "cd-dg-expander" }, parent);
    svg("rect", {
      x: cx - EXPANDER / 2, y: cy - EXPANDER / 2, width: EXPANDER, height: EXPANDER
    }, group);
    var d = "M" + (cx - 3) + " " + cy + "H" + (cx + 3);
    if (!open) d += "M" + cx + " " + (cy - 3) + "V" + (cy + 3);
    svg("path", { d: d }, group);
  }

  /* ---- the mounted diagram ---- */

  function mount(container, api) {
    var shape = structure(api.model);
    var open = {};            // key -> true for every expanded element
    var selectedKey = null;
    var selectedPath = null;  // the path the viewer was last told of
    var cursorKey = null;
    var view = { scale: 1, x: MARGIN, y: MARGIN };
    var current = null;       // the last layout
    var byKey = {};           // key -> box of the last layout
    var widthCache = {};

    container.textContent = "";
    if (!shape.root) {
      var empty = document.createElement("p");
      empty.className = "cd-empty";
      empty.textContent = "The model contains no tree.";
      container.appendChild(empty);
      return {
        show: function () { return false; },
        focus: function () {},
        view: function () { return { scale: 1, x: 0, y: 0 }; }
      };
    }

    var canvas = svg("svg", {
      "class": "cd-dg-svg", role: "tree", "aria-label": "Instance diagram"
    }, container);
    var probe = svg("text", { "class": "cd-dg-probe", x: -1000, y: -1000 }, canvas);
    var viewport = svg("g", { "class": "cd-dg-view" }, canvas);
    var linkLayer = svg("g", { "class": "cd-dg-links" }, viewport);
    var itemLayer = svg("g", { "class": "cd-dg-items" }, viewport);

    open[shape.root.key] = true;
    cursorKey = shape.root.key;

    // A pane that is not laid out measures nothing. The estimate keeps the
    // boxes readable until the next render measures for real, and is not
    // cached, so that render does.
    function textWidth(text, className) {
      var id = className + "\u0000" + text;
      if (widthCache[id] !== undefined) return widthCache[id];
      probe.setAttribute("class", "cd-dg-probe " + className);
      probe.textContent = text;
      var width = probe.getComputedTextLength ? probe.getComputedTextLength() : 0;
      if (!width) return text.length * 7.5;
      widthCache[id] = width;
      return width;
    }

    function typeLine(item) {
      return item.kind === "element" && item.type ? api.typeRef(item.type) : null;
    }

    function measure(item) {
      if (item.kind === "group") return { w: GROUP_W, h: GROUP_H };
      var ref = typeLine(item);
      var w = textWidth(item.name, "cd-dg-name");
      if (ref) w = Math.max(w, textWidth(ref.label, "cd-dg-type-text"));
      // The expander sits on the right edge, half inside the box.
      return { w: Math.ceil(w) + 2 * PAD_X + EXPANDER / 2, h: ref ? LINE_TWO : LINE_ONE };
    }

    function isOpen(item) {
      return item.kind === "group" || (item.expandable && !!open[item.key]);
    }

    function applyView() {
      viewport.setAttribute(
        "transform", "translate(" + view.x + " " + view.y + ") scale(" + view.scale + ")"
      );
    }

    function level(box) {
      var count = 1;
      for (var p = box.parent; p; p = p.parent) if (p.item.kind === "element") count++;
      return count;
    }

    function connector(box) {
      var cy = box.y + box.h / 2;
      var from = box.x + box.w + (box.item.kind === "element" ? EXPANDER / 2 : 0);
      var bus = current.columns[box.depth + 1] - COLUMN_GAP / 2;
      var top = cy;
      var bottom = cy;
      var d = "M" + from + " " + cy + "H" + bus;
      for (var i = 0; i < box.children.length; i++) {
        var child = box.children[i];
        var middle = child.y + child.h / 2;
        top = Math.min(top, middle);
        bottom = Math.max(bottom, middle);
        d += "M" + bus + " " + middle + "H" + child.x;
      }
      return d + "M" + bus + " " + top + "V" + bottom;
    }

    function drawItem(box) {
      var item = box.item;
      var x = box.x;
      var y = box.y;
      var w = box.w;
      var h = box.h;
      var classes = "cd-dg-item cd-dg-" + item.kind;
      if (item.min === 0) classes += " cd-dg-optional";
      if (isRepeated(item)) classes += " cd-dg-repeated";
      if (item.key === selectedKey) classes += " cd-dg-selected";
      if (item.key === cursorKey) classes += " cd-dg-cursor";
      var g = svg("g", { "class": classes, "data-key": item.key }, itemLayer);

      if (item.kind === "group") {
        g.setAttribute("data-compositor", item.compositor);
        svg("title", {}, g).textContent = api.gloss(item.compositor);
        if (isRepeated(item)) {
          svg("path", { "class": "cd-dg-shadow", d: octagon(x + STACK, y + STACK, w, h) }, g);
        }
        svg("path", { "class": "cd-dg-frame", d: octagon(x, y, w, h) }, g);
        drawSymbol(g, item.compositor, x + w / 2, y + h / 2);
      } else {
        if (isRepeated(item)) {
          svg("rect", { "class": "cd-dg-shadow", x: x + STACK, y: y + STACK, width: w, height: h }, g);
        }
        svg("rect", { "class": "cd-dg-frame", x: x, y: y, width: w, height: h }, g);
        svg("rect", { "class": "cd-dg-ring", x: x - 3, y: y - 3, width: w + 6, height: h + 6, rx: 2 }, g);
        svg("text", { "class": "cd-dg-name", x: x + PAD_X, y: y + 15 }, g).textContent = item.name;
      }

      if (item.kind === "element") {
        g.setAttribute("data-path", item.path.join("/"));
        var ref = typeLine(item);
        if (ref) {
          var holder = g;
          if (ref.link) {
            holder = svg("a", { "class": "cd-dg-type", "data-type": item.type }, g);
            if (ref.href) holder.setAttribute("href", ref.href);
          }
          svg("text", { "class": "cd-dg-type-text", x: x + PAD_X, y: y + 28 }, holder)
            .textContent = ref.label;
        }
        if (item.selectable) {
          g.setAttribute("role", "treeitem");
          g.setAttribute("aria-level", String(level(box)));
          g.setAttribute("aria-selected", String(item.key === selectedKey));
          g.setAttribute("aria-label", item.name);
          g.setAttribute("tabindex", item.key === cursorKey ? "0" : "-1");
          if (item.expandable) g.setAttribute("aria-expanded", String(!!open[item.key]));
        }
        if (item.expandable) {
          drawExpander(g, x + w, y + h / 2, !!open[item.key]);
        } else if (item.recursive) {
          var mark = svg("text", { "class": "cd-dg-recursive", x: x + w + 3, y: y + h / 2 + 4 }, g);
          mark.textContent = "\u21BB";
          svg("title", {}, mark).textContent =
            "This type already appears further up this path; open it there.";
        }
      }

      var card = cardinality(item);
      if (card) {
        svg("text", {
          "class": "cd-dg-card", x: x + w, y: y + h + STACK + 10, "text-anchor": "end"
        }, g).textContent = card;
      }
    }

    // Every box is drawn anew, the focused one included, so the keyboard is
    // handed back to the cursor if it was in the drawing before.
    function draw() {
      var hadFocus = canvas.contains(document.activeElement);
      linkLayer.textContent = "";
      itemLayer.textContent = "";
      var d = "";
      for (var i = 0; i < current.boxes.length; i++) {
        var box = current.boxes[i];
        if (box.children.length) d += connector(box);
        drawItem(box);
      }
      svg("path", { "class": "cd-dg-link", d: d }, linkLayer);
      if (hadFocus) focus();
    }

    // The nearest drawn ancestor of a key that is no longer drawn: keys are
    // positions, so an ancestor's key is a prefix.
    function drawnKey(key) {
      while (key && !byKey[key]) {
        var cut = key.lastIndexOf(".");
        key = cut === -1 ? null : key.slice(0, cut);
      }
      return key || shape.root.key;
    }

    // Lays out again and draws. `anchorKey` names a box that must not move on
    // screen — the one just opened or closed.
    function render(anchorKey) {
      var anchor = anchorKey && byKey[anchorKey] ? byKey[anchorKey] : null;
      var before = anchor
        ? { x: view.x + anchor.x * view.scale, y: view.y + anchor.y * view.scale }
        : null;
      current = layout(shape.root, shape.children, isOpen, measure);
      byKey = {};
      for (var i = 0; i < current.boxes.length; i++) byKey[current.boxes[i].item.key] = current.boxes[i];
      if (before && byKey[anchorKey]) {
        view.x = before.x - byKey[anchorKey].x * view.scale;
        view.y = before.y - byKey[anchorKey].y * view.scale;
      }
      cursorKey = drawnKey(cursorKey);
      draw();
      applyView();
    }

    function toggle(item) {
      if (!item.expandable) return;
      if (open[item.key]) delete open[item.key];
      else open[item.key] = true;
      render(item.key);
    }

    function choose(item, focusDetail) {
      if (!item.selectable) return;
      selectedKey = item.key;
      selectedPath = item.path.join("/");
      cursorKey = item.key;
      draw();
      api.select(item.path, focusDetail);
    }

    function visibleWidth() {
      return Math.max(0, canvas.clientWidth - (api.covered ? api.covered() : 0));
    }

    // Pans the box into the part of the pane the reader can see: always to
    // its middle with `always`, otherwise only when it is not wholly in view.
    function reveal(box, always) {
      if (!box) return;
      var width = visibleWidth();
      var height = canvas.clientHeight;
      var s = view.scale;
      var left = view.x + box.x * s;
      var top = view.y + box.y * s;
      var inside = left >= MARGIN && top >= MARGIN
        && left + box.w * s <= width - MARGIN && top + box.h * s <= height - MARGIN;
      if (inside && !always) return;
      view.x = width / 2 - (box.x + box.w / 2) * s;
      view.y = height / 2 - (box.y + box.h / 2) * s;
      applyView();
    }

    function show(path, centre) {
      var chain = shape.find(path);
      if (!chain) {
        render(null);
        return false;
      }
      for (var i = 0; i < chain.length - 1; i++) open[chain[i].key] = true;
      var wanted = path.join("/");
      // The box the reader clicked keeps the mark when the viewer answers
      // with the same path, even where another box shares it.
      if (selectedPath !== wanted || !selectedKey) {
        selectedKey = chain[chain.length - 1].key;
        selectedPath = wanted;
      }
      cursorKey = selectedKey;
      render(null);
      reveal(byKey[selectedKey], !!centre);
      return true;
    }

    function focus() {
      var node = itemLayer.querySelector('[data-key="' + cursorKey + '"]');
      if (node && node.focus) node.focus({ preventScroll: true });
    }

    canvas.addEventListener("click", function (event) {
      var itemNode = event.target.closest(".cd-dg-item");
      if (!itemNode) return;
      var box = byKey[itemNode.getAttribute("data-key")];
      if (!box) return;
      if (event.target.closest(".cd-dg-expander")) {
        toggle(box.item);
        return;
      }
      var link = event.target.closest(".cd-dg-type");
      if (link) {
        // A modified click is the reader asking for the page itself; the
        // browser follows the href. A plain one keeps the diagram and shows
        // the type beside it, the bargain `typeCell` makes in the tables.
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) return;
        event.preventDefault();
        choose(box.item, false);
        api.showType(link.getAttribute("data-type"));
        return;
      }
      choose(box.item, false);
    });

    canvas.addEventListener("dblclick", function (event) {
      var itemNode = event.target.closest(".cd-dg-item");
      if (!itemNode || event.target.closest(".cd-dg-expander")) return;
      var box = byKey[itemNode.getAttribute("data-key")];
      if (box) toggle(box.item);
    });

    render(null);

    return {
      show: show,
      focus: focus,
      view: function () { return { scale: view.scale, x: view.x, y: view.y }; }
    };
  }
```

Change the export to:

```js
  window.CpacsDiagram = {
    structure: structure,
    layout: layout,
    mount: mount
  };
```

- [ ] **Step 4: Add the diagram styles** — append to `src/cpacs_doc/assets/styles.css`:

```css
/* ---- the diagram (planning/specs/2026-09-30-diagram-view-design.md) ----
   Every colour comes from the custom properties above, so the theme button and
   the dark palette reach the drawing without a line of script. */
.cd-pane.cd-diagram { position: relative; overflow: hidden; }
.cd-diagram[hidden] { display: none; }
.cd-dg-svg {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
  user-select: none;
  font-family: var(--face-text);
}
.cd-dg-svg:active { cursor: grabbing; }
.cd-dg-probe { visibility: hidden; }
.cd-dg-link { fill: none; stroke: var(--rule-strong); stroke-width: 1; }
.cd-dg-frame, .cd-dg-shadow { fill: var(--page); stroke: var(--ink-soft); stroke-width: 1; }
.cd-dg-optional > .cd-dg-frame, .cd-dg-optional > .cd-dg-shadow { stroke-dasharray: 4 1; }
.cd-dg-item[role="treeitem"] { cursor: pointer; }
.cd-dg-item:focus { outline: none; }
.cd-dg-name { fill: var(--ink); font-size: 13px; }
.cd-dg-type-text { fill: var(--ink-soft); font-size: 11px; font-family: var(--face-code); }
.cd-dg-type .cd-dg-type-text { fill: var(--link); }
.cd-dg-type:hover .cd-dg-type-text { text-decoration: underline; }
.cd-dg-card { fill: var(--ink-soft); font-size: 10px; font-family: var(--face-code); }
.cd-dg-symbol-line { fill: none; stroke: var(--ink); stroke-width: 1; }
.cd-dg-symbol-dot { fill: var(--ink); }
.cd-dg-expander { cursor: pointer; }
.cd-dg-expander rect { fill: var(--page); stroke: var(--ink-soft); stroke-width: 1; }
.cd-dg-expander path { fill: none; stroke: var(--ink); stroke-width: 1.2; }
.cd-dg-recursive { fill: var(--ink-soft); font-size: 12px; }
.cd-dg-selected > .cd-dg-frame { stroke: var(--ink); stroke-width: 2; }
/* The cursor mark and the focus ring are two things (0016): the mark says
   where the keys act, the ring that the keyboard is here at all. */
.cd-dg-ring { fill: none; stroke: none; }
.cd-dg-cursor > .cd-dg-ring { stroke: var(--ink-soft); stroke-dasharray: 2 2; }
.cd-dg-item:focus-visible > .cd-dg-ring { stroke: var(--focus); stroke-width: 2; stroke-dasharray: none; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram.py -q`
Expected: 26 passed

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed

---

### Task 5: The view inside the viewer

**Files:**
- Modify: `src/cpacs_doc/assets/viewer.js` (constants and `state` at 19-42, `parseLocation` 56-76, `select` 886-902, Escape and `/` in `setupGlobalKeys` 805-856, `backToTree` 468-471, `setupTabs` 2368-2409, `showPane` 2449-2458, `start` 2526-2584, `restore` 2586-2602)
- Modify: `src/cpacs_doc/assets/styles.css` (append)
- Create: `tests/test_viewer_diagram_view.py`

**Interfaces:**
- Consumes: `CpacsDiagram.mount(container, api)` and its `show / focus / view` (Task 4).
- Produces (inside `viewer.js`): `state.view` (`"tree" | "diagram"`), `state.diagram` (the controller), `setView(view, push)`, `openOverlay()`, `closeOverlay()`, `overlayIsOpen()`, `select(path, focusAfter)` (second argument new and optional).

- [ ] **Step 1: Write the failing tests** — create `tests/test_viewer_diagram_view.py`

```python
"""The diagram as a view of the viewer: its address, its overlay, its tab.

The diagram's own parts are held to their contract in `test_viewer_diagram.py`;
here the question is whether the viewer around it behaves — the route names
the view, a click writes the address, the documentation stands over the
diagram and goes away again, and the reader can get in and back out.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import cdp

from cpacs_doc import generator, serve as serve_module

FIXTURES = Path(__file__).parent / "fixtures"

SCHEMA = "diagram.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

DRAWN = "return document.querySelectorAll('.cd-dg-item').length > 1;"
HEADING = "return (document.querySelector('#cd-detail h1') || {}).textContent || null;"


@pytest.fixture(scope="module")
def viewer(browser, base):
    """The hint stays out of the way; the tests about it open it themselves."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for("return !!document.querySelector('.cd-node');", "the tree")
    browser.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )
    return browser


def at(viewer, base, path: str):
    viewer.open(base + path)
    viewer.wait_for(DRAWN, "the diagram")
    return viewer


def centre(page, selector: str):
    return page.evaluate(
        f"var r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + r.height / 2];"
    )


def item(path: str, part: str = ".cd-dg-frame") -> str:
    return f'.cd-dg-item[data-path="{path}"] {part}'


def overlay_open(page) -> bool:
    return page.evaluate(
        "return getComputedStyle(document.getElementById('cd-detail')).display !== 'none';"
    )


def selected(page):
    return page.evaluate(
        "var s = document.querySelector('.cd-dg-selected');"
        " return s ? s.getAttribute('data-path') : null;"
    )


def test_the_diagram_route_opens_the_diagram_view(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    assert page.evaluate("""
      function shown(id) { var n = document.getElementById(id); return !!n && n.offsetParent !== null; }
      return {
        app: document.getElementById('cd-app').classList.contains('cd-app-diagram'),
        diagram: shown('cd-diagram'), tree: shown('cd-tree'),
        tab: document.getElementById('cd-tab-diagram').getAttribute('aria-selected'),
        search: shown('cd-tab-search'), treeTab: shown('cd-tab-tree'),
        splitter: shown('cd-splitter')
      };
    """) == {"app": True, "diagram": True, "tree": False, "tab": "true",
             "search": False, "treeTab": True, "splitter": False}
    assert overlay_open(page) is False


def test_the_diagram_fills_the_width(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    width = page.evaluate(
        "return document.getElementById('cd-diagram').getBoundingClientRect().width"
        " / window.innerWidth;"
    )
    assert width > 0.9


def test_a_path_selects_centres_and_documents(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/wings/wing/span/")
    assert selected(page) == "wings/wing/span"
    assert overlay_open(page)
    assert page.evaluate(HEADING) == "span"
    x, y = centre(page, item("wings/wing/span"))
    visible = page.evaluate(
        "var d = document.getElementById('cd-diagram').getBoundingClientRect();"
        " var o = document.getElementById('cd-detail').getBoundingClientRect();"
        " return [d.left, o.left, d.top, d.bottom];"
    )
    assert visible[0] < x < visible[1], "the selection is not beside the overlay"
    assert visible[2] < y < visible[3]


def test_a_click_selects_and_writes_the_address(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    page.click(*centre(page, item("header")))
    page.wait_for("return location.pathname === '/diagram/cpacs/header/';", "the address")
    assert page.evaluate(HEADING) == "header"
    assert overlay_open(page)
    assert selected(page) == "header"


def test_the_type_line_opens_the_type_documentation(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    page.click(*centre(page, item("header", ".cd-dg-type-text")))
    page.wait_for(
        "return (document.querySelector('#cd-detail h1') || {}).textContent === 'settingsType';",
        "the type",
    )
    assert page.evaluate("return location.pathname;") == "/diagram/cpacs/header/"
    assert overlay_open(page)


def test_the_overlay_closes_with_its_button_and_with_escape(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/header/")
    assert overlay_open(page)
    page.click(*centre(page, "#cd-overlay-close"))
    assert overlay_open(page) is False
    page.click(*centre(page, item("wings")))
    assert overlay_open(page)
    page.press("Escape")
    assert overlay_open(page) is False


def test_the_tabs_switch_views_and_keep_the_selection(viewer, base):
    viewer.open(base + "/tree/cpacs/wings/")
    viewer.wait_for("return !!document.querySelector('.cd-node');", "the tree")
    viewer.click(*centre(viewer, "#cd-tab-diagram"))
    viewer.wait_for(DRAWN, "the diagram")
    assert viewer.evaluate("return location.pathname;") == "/diagram/cpacs/wings/"
    assert selected(viewer) == "wings"
    viewer.click(*centre(viewer, "#cd-tab-tree"))
    viewer.wait_for("return location.pathname === '/tree/cpacs/wings/';", "the tree address")
    assert viewer.evaluate(
        "return document.getElementById('cd-tree').offsetParent !== null"
        " && !document.getElementById('cd-app').classList.contains('cd-app-diagram');"
    )
    assert viewer.evaluate(HEADING) == "wings"


def test_back_returns_across_views(viewer, base):
    """Review Focus 4: the view follows the address, both ways."""
    viewer.open(base + "/tree/cpacs/header/")
    viewer.wait_for("return !!document.querySelector('.cd-node');", "the tree")
    viewer.click(*centre(viewer, "#cd-tab-diagram"))
    viewer.wait_for(DRAWN, "the diagram")
    viewer.click(*centre(viewer, item("wings")))
    viewer.wait_for("return location.pathname === '/diagram/cpacs/wings/';", "the click")
    viewer.evaluate("history.back(); return true;")
    viewer.wait_for("return location.pathname === '/diagram/cpacs/header/';", "back once")
    assert selected(viewer) == "header"
    viewer.evaluate("history.back(); return true;")
    viewer.wait_for("return location.pathname === '/tree/cpacs/header/';", "back twice")
    viewer.wait_for(
        "return !document.getElementById('cd-app').classList.contains('cd-app-diagram');",
        "the tree view",
    )
    assert viewer.evaluate(HEADING) == "header"


def test_an_unknown_path_is_reported(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/nope/")
    assert page.evaluate(HEADING) == "Not found"
    assert page.evaluate("return !!document.querySelector('.cd-dg-item[data-path=\"\"]');")


@pytest.fixture(scope="module")
def single(tmp_path_factory):
    directory = tmp_path_factory.mktemp("single")
    schema = directory / SCHEMA
    shutil.copyfile(FIXTURES / SCHEMA, schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=directory / "media", limit=0
    )
    assert site.rebuild()
    generator.generate_single(site.model, directory)
    return (directory / generator.SINGLE_NAME).as_uri()


def test_the_one_file_form_opens_the_diagram_from_its_fragment(viewer, single):
    """No type pages are written in this form, so the type line switches the
    panel and carries no address."""
    viewer.open(single + "#/diagram/cpacs/header/")
    viewer.wait_for(DRAWN, "the diagram")
    assert selected(viewer) == "header"
    assert viewer.evaluate(HEADING) == "header"
    assert viewer.evaluate(
        "return document.querySelector('.cd-dg-item[data-path=\"header\"] a.cd-dg-type')"
        ".hasAttribute('href');"
    ) is False
    viewer.click(*centre(viewer, item("wings")))
    viewer.wait_for("return location.hash === '#/diagram/cpacs/wings/';", "the fragment")


def test_twin_paths_select_the_box_that_was_clicked(browser, tmp_path):
    """Review Focus 1. `minimal.xsd` has `shared` in both branches of a choice:
    one path, two boxes. The mark goes to the box the reader clicked, through
    the viewer's `select` and its `show` for the same path."""
    import threading

    schema = tmp_path / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)
    site = serve_module.Site(schema, None, media_expected=False,
                             media_root=tmp_path / "media", limit=0)
    assert site.rebuild()
    server = serve_module.create_server(site, "127.0.0.1", 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = f"http://127.0.0.1:{server.server_address[1]}"
        browser.open(address + "/diagram/cpacs/")
        browser.wait_for(DRAWN, "the diagram")
        keys = browser.evaluate("""
          var twins = document.querySelectorAll('.cd-dg-item[data-path="shared"]');
          if (twins.length !== 2) return null;
          twins[1].querySelector('.cd-dg-frame')
            .dispatchEvent(new MouseEvent('click', { bubbles: true }));
          var marked = document.querySelectorAll('.cd-dg-item.cd-dg-selected');
          return [twins[1].getAttribute('data-key'),
                  Array.prototype.map.call(marked, function (m) { return m.getAttribute('data-key'); })];
        """)
        assert keys is not None, "minimal.xsd no longer has two `shared` boxes"
        assert keys[1] == [keys[0]]
    finally:
        browser.open("about:blank")
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q`
Expected: FAIL — `/diagram/cpacs/` renders "This address does not exist" (no `.cd-dg-item`, `TimeoutError: the diagram did not appear`).

- [ ] **Step 3: Route and state** — in `viewer.js`:

After `var TREE_SEGMENT = "/tree/";` add:

```js
  var DIAGRAM_SEGMENT = "/diagram/";
```

In `state` add after `tab: "tree"` (put a comma after `"tree"`):

```js
    view: "tree",      // "tree" or "diagram": which picture of the tree is up
    diagram: null      // the mounted diagram, made on the first visit
```

Replace `parseLocation` (lines 56-76) with:

```js
  // The view is named by the address, /tree/ or /diagram/, and the path after
  // it means the same in both. Whichever segment comes first wins, so an
  // element that happens to be called "diagram" deep in a tree path stays a
  // tree path.
  function routeIn(text) {
    var tree = text.indexOf(TREE_SEGMENT);
    var diagram = text.indexOf(DIAGRAM_SEGMENT);
    if (tree === -1 && diagram === -1) return null;
    var isDiagram = diagram !== -1 && (tree === -1 || diagram < tree);
    var at = isDiagram ? diagram : tree;
    return {
      at: at,
      view: isDiagram ? "diagram" : "tree",
      rest: text.slice(at + (isDiagram ? DIAGRAM_SEGMENT : TREE_SEGMENT).length)
    };
  }

  function parseLocation() {
    var pathname = decodeURIComponent(window.location.pathname);
    var route = routeIn(pathname);
    if (route === null) {
      // One file is opened under its own name, so its path says nothing about
      // where the reader is; the fragment carries that instead. An absent
      // fragment is the root of the tree rather than a 404 — there is no other
      // document here that could have been meant.
      if (!singleFile()) return null;
      var inFragment = routeIn(decodeURIComponent(window.location.hash.slice(1)));
      return {
        root: ".",
        view: inFragment ? inFragment.view : "tree",
        segments: inFragment ? segmentsOf(inFragment.rest) : []
      };
    }
    return {
      root: pathname.slice(0, route.at),
      view: route.view,
      segments: segmentsOf(route.rest)
    };
  }
```

Replace `select` (lines 886-902) with:

```js
  function addressFor(path) {
    // The root element is part of the URL: it is part of an instance path, and
    // the "show in tree" links on type pages are written that way.
    var segments = [declaration(state.model.tree).name].concat(path);
    var address = (state.view === "diagram" ? DIAGRAM_SEGMENT : TREE_SEGMENT)
      + segments.join("/") + "/";
    // The fragment is the only part of a file:// URL a page may change:
    // pushState to a path throws a SecurityError against a null origin.
    return singleFile() ? "#" + address : state.root + address;
  }

  function select(path, focusAfter) {
    state.shownType = null;
    state.shownSection = null;
    state.path = path;
    state.cursor = path;
    expandAncestors(path);
    window.history.pushState({ path: path }, "", addressFor(path));
    if (state.view === "diagram") {
      openOverlay();
      state.diagram.show(path, false);
    } else {
      renderTree();
    }
    renderDetail();
    if (focusAfter) focusDetail();
  }
```

- [ ] **Step 4: The view switch, the overlay and the diagram's API** — add after `select`:

```js
  /* ---- the diagram view ----
   *
   * The same tree, drawn instead of listed (spec 2026-09-30). The selection is
   * shared, so either view opens where the other left off; what is expanded is
   * each view's own. In the diagram's view the grid has one column, and the
   * detail panel — the same element, rendered by the same code — stands over
   * the right edge of the drawing until it is closed.
   */
  function setView(view, push) {
    state.view = view;
    document.getElementById("cd-app").classList.toggle("cd-app-diagram", view === "diagram");
    if (view === "diagram") {
      // Shown before it is mounted: a pane that is not laid out measures no
      // text, and the boxes are sized by what it measures.
      showPane("diagram");
      if (!state.diagram) {
        state.diagram = window.CpacsDiagram.mount(document.getElementById("cd-diagram"), diagramApi());
      }
      state.diagram.show(state.path, true);
    } else {
      closeOverlay();
      showPane("tree");
      expandAncestors(state.path);
      renderTree();
    }
    if (push) window.history.pushState({ path: state.path }, "", addressFor(state.path));
  }

  function openOverlay() {
    document.getElementById("cd-app").classList.add("cd-detail-open");
  }

  function closeOverlay() {
    document.getElementById("cd-app").classList.remove("cd-detail-open");
  }

  function overlayIsOpen() {
    return state.view === "diagram"
      && document.getElementById("cd-app").classList.contains("cd-detail-open");
  }

  function setupOverlay() {
    var close = document.getElementById("cd-overlay-close");
    if (!close) return;
    close.addEventListener("click", function () {
      closeOverlay();
      if (state.diagram) state.diagram.focus();
    });
  }

  function diagramApi() {
    return {
      model: state.model,
      select: function (path, focusAfter) { select(path, focusAfter); },
      showType: function (typeName) {
        openOverlay();
        showType(typeName);
      },
      typeRef: diagramTypeRef,
      gloss: compositorGloss,
      covered: function () {
        return overlayIsOpen() ? document.getElementById("cd-detail").offsetWidth : 0;
      }
    };
  }

  // What the type line of a box says and whether it leads anywhere: the label
  // the tables use, a link where the model has the type, plain text for a
  // built-in one. The one-file form writes no type pages, so there the line
  // switches the panel and carries no address.
  function diagramTypeRef(typeName) {
    if (!typeName) return null;
    var type = state.model.types[typeName];
    if (!type) return { label: typeName, link: false };
    if (type.anonymous && !type.base) return null;
    var ref = { label: typeLabel(typeName), link: true };
    if (!singleFile()) ref.href = typeHref(typeName);
    return ref;
  }
```

- [ ] **Step 5: Tabs, panes, keys** — in `viewer.js`:

In `setupTabs`, after `label("cd-search-panel", "cd-tab-search");` add:

```js
    label("cd-diagram", "cd-tab-diagram");
```

Replace the click listener body's three `if` lines with:

```js
      if (tab.id === "cd-tab-docs") { renderDocs(); showPane("docs"); }
      else if (tab.id === "cd-tab-tree") {
        if (state.view === "diagram") setView("tree", true);
        showPane("tree");
        focusCursor();
      }
      else if (tab.id === "cd-tab-search") { showPane("search"); focusSearch(); }
      else if (tab.id === "cd-tab-diagram") {
        if (state.view !== "diagram") setView("diagram", true);
        state.diagram.focus();
      }
```

In the strip's keydown handler replace `if (!all[i].hidden) shown.push(all[i]);` with:

```js
      // Hidden by the attribute or by the view: the diagram's view keeps only
      // Tree and Diagram in the strip.
      for (var i = 0; i < all.length; i++) {
        if (!all[i].hidden && all[i].offsetParent !== null) shown.push(all[i]);
      }
```

(the `for` line it replaces is `for (var i = 0; i < all.length; i++) if (!all[i].hidden) shown.push(all[i]);`).

In `showPane` add after the `cd-docs` line:

```js
    var diagramPane = document.getElementById("cd-diagram");
    if (diagramPane) diagramPane.hidden = name !== "diagram";
```

and after `markTab("cd-tab-search", name === "search");`:

```js
    markTab("cd-tab-diagram", name === "diagram");
```

Replace `backToTree`:

```js
  function backToTree() {
    if (state.view === "diagram") {
      if (state.diagram) state.diagram.focus();
      return;
    }
    if (docsAreOpen()) showPane("tree");
    focusCursor();
  }
```

In `setupGlobalKeys`:

- in the `/` branch, first line: `if (state.view === "diagram") return;`
- replace the Escape/Backspace resolution chain with:

```js
        if (!document.getElementById("cd-search-panel").hidden) {
          closeSearch(true);
        } else if (inDetail(event.target)) {
          backToTree();
        } else if (overlayIsOpen()) {
          // Out of the panel is the nearer thing; closing it the next.
          closeOverlay();
          backToTree();
        } else if (document.getElementById("cd-hint")) {
          hideHint();
        } else {
          backToTree();
        }
```

- in the body-target arrow branch replace `hintStart(); focusCursor();` with:

```js
          if (state.view === "diagram") {
            backToTree();
          } else {
            hintStart();
            focusCursor();
          }
```

- [ ] **Step 6: Start and restore** — in `start()`:

After `setupHelp();` add `setupOverlay();`. In `show(model)`, after `setupHint();` add:

```js
      if (location.view === "diagram") {
        // An address that names a place asks for its documentation; the bare
        // diagram does not. Opened before the view is set up, so the place is
        // centred in what the overlay leaves visible.
        if (segments.length) openOverlay();
        setView("diagram", false);
      }
```

Replace `restore()` with:

```js
  function restore() {
    var location = parseLocation();
    if (!location || !state.model) return;
    var segments = location.segments;
    var rootName = declaration(state.model.tree).name;
    if (segments.length && segments[0] === rootName) segments = segments.slice(1);
    // The address names a tree path, so that is what the panel must show: a
    // type or a section standing in front of it belongs to the place the
    // reader has just left. `select` clears them for the same reason.
    state.shownType = null;
    state.shownSection = null;
    state.path = segments;
    state.cursor = segments;
    expandAncestors(segments);
    // The overlay first, for the same reason as in `start`.
    if (location.view === "diagram") {
      if (segments.length) openOverlay();
      else closeOverlay();
    }
    if (location.view !== state.view) {
      setView(location.view, false);
    } else if (state.view === "diagram") {
      state.diagram.show(segments, true);
    } else {
      renderTree();
    }
    renderDetail();
  }
```

- [ ] **Step 7: Layout of the view** — append to `styles.css`:

```css
/* One column in the diagram's view: the column's strip is the header, the
   diagram its pane, and the splitter has nothing left to divide. */
.cd-app.cd-app-diagram { grid-template-columns: minmax(0, 1fr); }
.cd-app-diagram .cd-splitter { display: none; }
.cd-app-diagram #cd-tab-search,
.cd-app-diagram #cd-tab-docs { display: none; }
/* The detail panel is the same element, standing over the drawing's right
   edge while something is chosen. */
.cd-app-diagram .cd-pane-detail { display: none; }
.cd-app-diagram.cd-detail-open .cd-pane-detail {
  display: block;
  position: fixed;
  top: 1.1rem;
  right: 1.4rem;
  bottom: 1.1rem;
  width: clamp(22rem, 40vw, 48rem);
  box-sizing: border-box;
  padding: 2.4rem 1.2rem 1rem;
  background: var(--page);
  border: 1px solid var(--rule);
  border-radius: 6px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
  overflow: auto;
  z-index: 20;
}
.cd-overlay-close { display: none; }
.cd-app-diagram.cd-detail-open .cd-overlay-close {
  display: block;
  position: fixed;
  top: 1.6rem;
  right: 2rem;
  z-index: 21;
  width: 1.8rem;
  height: 1.8rem;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  background: var(--page);
  color: var(--ink-soft);
  font: inherit;
  line-height: 1;
  cursor: pointer;
}
.cd-app-diagram.cd-detail-open .cd-overlay-close:hover { color: var(--ink); border-color: var(--ink); }
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q`
Expected: 11 passed

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed. If a tree keyboard test fails on Escape, check that `overlayIsOpen()` returns `false` in the tree view (it tests `state.view` first).

---

### Task 6: Zoom and pan

**Files:**
- Modify: `tests/cdp.py` (`KEYS`, add `wheel`, `drag`)
- Modify: `src/cpacs_doc/assets/diagram.js` (inside `mount`)
- Modify: `src/cpacs_doc/assets/styles.css` (append toolbar)
- Test: `tests/test_viewer_diagram_view.py`

**Interfaces:**
- Consumes: `mount` internals `view`, `applyView`, `current`, `byKey`, `selectedKey`, `reveal`, `visibleWidth` (Task 4).
- Produces: toolbar buttons `#cd-dg-zoom-out`, `#cd-dg-zoom-in`, `#cd-dg-zoom-reset`, `#cd-dg-fit`, `#cd-dg-centre`; internal `zoomAt(factor, px, py)`, `zoomBy(factor)`, `setScale(scale)` used by Task 7. `cdp.Browser.wheel(x, y, delta_y, ctrl=False, shift=False)`, `cdp.Browser.drag(x0, y0, x1, y1, steps=5)`.

- [ ] **Step 1: Extend the driver** — in `tests/cdp.py` add to `KEYS`:

```python
    "+": (107, "NumpadAdd"), "-": (109, "NumpadSubtract"), "0": (48, "Digit0"),
```

and after `click`:

```python
    def wheel(self, x: float, y: float, delta_y: float, *,
              ctrl: bool = False, shift: bool = False) -> None:
        # Modifier bits as the protocol counts them: Alt 1, Ctrl 2, Meta 4, Shift 8.
        self.command("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": delta_y,
            "modifiers": (2 if ctrl else 0) | (8 if shift else 0),
        })

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 5) -> None:
        self.command("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x0, "y": y0, "button": "left", "buttons": 1,
            "clickCount": 1,
        })
        for i in range(1, steps + 1):
            self.command("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "button": "left", "buttons": 1,
                "x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps,
            })
        self.command("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x1, "y": y1, "button": "left", "buttons": 0,
            "clickCount": 1,
        })
```

- [ ] **Step 2: Write the failing tests** — append to `tests/test_viewer_diagram_view.py`

```python
# ---- zoom and pan ----

TRANSFORM = """
  var t = document.querySelector('.cd-dg-view').getAttribute('transform');
  var m = /translate\\(([-\\d.e]+) ([-\\d.e]+)\\) scale\\(([-\\d.e]+)\\)/.exec(t);
  return [parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3])];
"""


def transform(page):
    return page.evaluate(TRANSFORM)


def empty_spot(page):
    """A point on the canvas that holds no box while the drawing sits at its
    start: the lower right corner. Only for a closed overlay, which covers it."""
    return page.evaluate(
        "var r = document.getElementById('cd-diagram').getBoundingClientRect();"
        " return [r.right - 60, r.bottom - 60];"
    )


def on_canvas(page):
    """A point on the canvas the overlay never covers, clear of the toolbar:
    near the left edge, above the bottom. The wheel acts wherever it lands."""
    return page.evaluate(
        "var r = document.getElementById('cd-diagram').getBoundingClientRect();"
        " return [r.left + 12, r.bottom - 80];"
    )


def test_ctrl_wheel_zooms_around_the_pointer(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    ratio = page.evaluate("return window.devicePixelRatio;")
    x, y = centre(page, item("header"))
    page.wheel(x, y, -200, ctrl=True)
    assert transform(page)[2] > 1
    after = centre(page, item("header"))
    assert abs(after[0] - x) < 1.5 and abs(after[1] - y) < 1.5
    # The browser's own zoom stayed out of it (Review Focus 5).
    assert page.evaluate("return window.devicePixelRatio;") == ratio


def test_the_wheel_pans(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    before = transform(page)
    page.wheel(*on_canvas(page), 100)
    after = transform(page)
    assert abs(after[1] - (before[1] - 100)) < 0.5 and after[0] == before[0]
    page.wheel(*on_canvas(page), 50, shift=True)
    assert abs(transform(page)[0] - (before[0] - 50)) < 0.5


def test_dragging_the_canvas_pans(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    before = transform(page)
    x, y = empty_spot(page)
    page.drag(x, y, x - 80, y - 40)
    after = transform(page)
    assert abs(after[0] - (before[0] - 80)) < 1 and abs(after[1] - (before[1] - 40)) < 1


def test_the_zoom_buttons_step_and_reset(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    page.click(*centre(page, "#cd-dg-zoom-in"))
    assert abs(transform(page)[2] - 1.25) < 1e-6
    page.click(*centre(page, "#cd-dg-zoom-out"))
    page.click(*centre(page, "#cd-dg-zoom-out"))
    assert abs(transform(page)[2] - 0.8) < 1e-6
    page.click(*centre(page, "#cd-dg-zoom-reset"))
    assert transform(page)[2] == 1


def test_fit_brings_everything_into_view(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/wings/wing/sections/section/profile/")
    page.click(*centre(page, "#cd-overlay-close"))
    page.wheel(*on_canvas(page), 2000)
    page.click(*centre(page, "#cd-dg-fit"))
    assert page.evaluate("""
      var pane = document.getElementById('cd-diagram').getBoundingClientRect();
      var out = [];
      document.querySelectorAll('.cd-dg-frame').forEach(function (f) {
        var r = f.getBoundingClientRect();
        if (r.left < pane.left || r.right > pane.right || r.top < pane.top || r.bottom > pane.bottom)
          out.push(f.parentNode.getAttribute('data-key'));
      });
      return out;
    """) == []


def test_centre_puts_the_selection_beside_the_overlay(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/header/")
    page.wheel(*on_canvas(page), 400)
    page.click(*centre(page, "#cd-dg-centre"))
    x, y = centre(page, item("header"))
    middle = page.evaluate(
        "var d = document.getElementById('cd-diagram').getBoundingClientRect();"
        " var o = document.getElementById('cd-detail').getBoundingClientRect();"
        " return [(d.left + o.left) / 2, (d.top + d.bottom) / 2];"
    )
    assert abs(x - middle[0]) < 3 and abs(y - middle[1]) < 3
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q -k "zoom or pan or fit or centre or wheel or drag"`
Expected: 6 FAIL (no scale change, `#cd-dg-zoom-in` missing)

- [ ] **Step 4: Implement** — in `mount`, before `render(null);` at the end, add:

```js
    /* ---- zoom and pan ---- */

    // The point under (px, py) stays where it is.
    function scaleAt(next, px, py) {
      view.x = px - (px - view.x) * next / view.scale;
      view.y = py - (py - view.y) * next / view.scale;
      view.scale = next;
      applyView();
    }

    function zoomAt(factor, px, py) {
      scaleAt(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, view.scale * factor)), px, py);
    }

    // Around the middle of what the reader can see, which is left of the
    // overlay while it is open.
    function zoomBy(factor) {
      zoomAt(factor, visibleWidth() / 2, canvas.clientHeight / 2);
    }

    // Exactly the scale asked for, not a product of factors that lands a
    // rounding error beside it.
    function setScale(scale) {
      scaleAt(scale, visibleWidth() / 2, canvas.clientHeight / 2);
    }

    function fit() {
      var width = visibleWidth();
      var height = canvas.clientHeight;
      var scale = Math.min(
        (width - 2 * MARGIN) / current.width, (height - 2 * MARGIN) / current.height, 1
      );
      view.scale = Math.max(ZOOM_MIN, scale);
      view.x = (width - current.width * view.scale) / 2;
      view.y = (height - current.height * view.scale) / 2;
      applyView();
    }

    // Not passive: an unhandled Ctrl+wheel is the browser zooming the whole
    // page, which is the one thing this gesture must not do here.
    canvas.addEventListener("wheel", function (event) {
      var rect = canvas.getBoundingClientRect();
      if (event.ctrlKey) {
        zoomAt(Math.exp(-event.deltaY * 0.002), event.clientX - rect.left, event.clientY - rect.top);
      } else if (event.shiftKey) {
        view.x -= event.deltaY || event.deltaX;
        applyView();
      } else {
        view.x -= event.deltaX;
        view.y -= event.deltaY;
        applyView();
      }
      event.preventDefault();
    }, { passive: false });

    // Dragging starts only on the canvas itself; on a box a press is a click.
    var drag = null;
    canvas.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest(".cd-dg-item")) return;
      drag = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
      if (canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!drag) return;
      view.x = drag.viewX + event.clientX - drag.x;
      view.y = drag.viewY + event.clientY - drag.y;
      applyView();
    });
    function endDrag() { drag = null; }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    var toolbar = document.createElement("div");
    toolbar.className = "cd-dg-toolbar";
    [
      ["cd-dg-zoom-out", "\u2212", "Zoom out", function () { zoomBy(0.8); }],
      ["cd-dg-zoom-in", "+", "Zoom in", function () { zoomBy(1.25); }],
      ["cd-dg-zoom-reset", "100 %", "Actual size", function () { setScale(1); }],
      ["cd-dg-fit", "Fit", "Fit the diagram into the window", fit],
      ["cd-dg-centre", "Centre", "Centre the selection",
        function () { reveal(byKey[selectedKey] || byKey[cursorKey], true); }]
    ].forEach(function (spec) {
      var button = document.createElement("button");
      button.type = "button";
      button.id = spec[0];
      button.textContent = spec[1];
      button.title = spec[2];
      button.setAttribute("aria-label", spec[2]);
      button.addEventListener("click", spec[3]);
      toolbar.appendChild(button);
    });
    container.appendChild(toolbar);
```

- [ ] **Step 5: Toolbar styles** — append to `styles.css`:

```css
.cd-dg-toolbar {
  position: absolute;
  left: 0.6rem;
  bottom: 0.6rem;
  display: flex;
  gap: 0.3rem;
}
.cd-dg-toolbar button {
  font: inherit;
  font-size: var(--step-0);
  padding: 0.15rem 0.55rem;
  border: 1px solid var(--rule-strong);
  border-radius: 4px;
  background: var(--page);
  color: var(--ink);
  cursor: pointer;
}
.cd-dg-toolbar button:hover { border-color: var(--ink); }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q`
Expected: 17 passed

- [ ] **Step 7: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed

---

### Task 7: Keyboard and the key legend

**Files:**
- Modify: `src/cpacs_doc/assets/diagram.js` (inside `mount`)
- Modify: `src/cpacs_doc/assets/viewer.js` (`HINT_GROUPS` at 569)
- Test: `tests/test_viewer_diagram_view.py`

**Interfaces:**
- Consumes: `toggle`, `choose`, `reveal`, `draw`, `focus`, `zoomBy`, `setScale`, `current`, `byKey`, `cursorKey`, `open` (Tasks 4, 6).
- Produces: key handling on `svg.cd-dg-svg`; a hint group with tab `"diagram"`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_viewer_diagram_view.py`

```python
# ---- keyboard ----

def cursor(page):
    return page.evaluate(
        "var c = document.querySelector('.cd-dg-cursor'); return c ? c.getAttribute('data-path') : null;"
    )


def keyed(viewer, base, path="/diagram/cpacs/"):
    page = at(viewer, base, path)
    page.evaluate("document.querySelector('.cd-dg-cursor').focus(); return true;")
    return page


def test_the_diagram_is_one_tab_stop(viewer, base):
    page = keyed(viewer, base)
    assert page.evaluate(
        "return document.querySelectorAll('.cd-dg-item[tabindex=\"0\"]').length;"
    ) == 1
    assert page.evaluate(
        "return document.activeElement.closest('[role=\"tree\"]').getAttribute('aria-label');"
    ) == "Instance diagram"


def test_right_opens_then_enters(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")                 # cpacs is open: into it
    assert cursor(page) == "header"
    page.press("ArrowRight")                 # header is closed: open it
    assert cursor(page) == "header"
    assert page.evaluate(
        "return document.querySelector('.cd-dg-item[data-path=\"header\"]').getAttribute('aria-expanded');"
    ) == "true"
    page.press("ArrowRight")                 # past the all: first element
    assert cursor(page) == "header/alpha"


def test_down_walks_the_siblings(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")                 # cpacs is open: into it
    assert cursor(page) == "header"
    page.press("ArrowDown")
    assert cursor(page) == "wings"
    page.press("ArrowDown")
    assert cursor(page) == "extras"
    page.press("ArrowUp")
    assert cursor(page) == "wings"
    page.press("Home")
    assert cursor(page) == "header"
    page.press("End")
    assert cursor(page) == "extras"


def test_down_past_the_last_sibling_stays_in_the_column(viewer, base):
    """beta is the last child of header; below it in the same column stands
    wing, a child of another parent."""
    page = keyed(viewer, base, "/diagram/cpacs/wings/wing/")
    page.evaluate("document.querySelector('#cd-overlay-close').click(); return true;")
    page.evaluate("""
      var header = document.querySelector('.cd-dg-item[data-path="header"]');
      header.querySelector('.cd-dg-expander')
        .dispatchEvent(new MouseEvent('click', { bubbles: true }));
      document.querySelector('.cd-dg-item[data-path="header/beta"] .cd-dg-frame')
        .dispatchEvent(new MouseEvent('click', { bubbles: true }));
      document.querySelector('.cd-dg-cursor').focus();
      return true;
    """)
    assert cursor(page) == "header/beta"
    page.press("ArrowDown")
    assert cursor(page) == "wings/wing"


def test_left_closes_then_climbs(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")
    page.press("ArrowRight")
    page.press("ArrowRight")
    assert cursor(page) == "header/alpha"
    page.press("ArrowLeft")                  # alpha does not open: to its parent
    assert cursor(page) == "header"
    page.press("ArrowLeft")                  # header is open: close it
    assert cursor(page) == "header"
    assert page.evaluate(
        "return document.querySelector('.cd-dg-item[data-path=\"header\"]').getAttribute('aria-expanded');"
    ) == "false"
    page.press("ArrowLeft")
    assert cursor(page) == ""


def test_space_selects_and_stays(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")
    page.press(" ")
    assert page.evaluate(HEADING) == "header"
    assert overlay_open(page)
    assert page.evaluate("return document.activeElement.getAttribute('data-path');") == "header"


def test_enter_selects_and_goes_there_escape_comes_back_then_closes(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")
    page.press("Enter")
    assert page.evaluate(
        "return document.getElementById('cd-detail').contains(document.activeElement);"
    )
    page.press("Escape")
    assert overlay_open(page)
    assert page.evaluate("return document.activeElement.getAttribute('data-path');") == "header"
    page.press("Backspace")
    assert overlay_open(page) is False


def test_the_zoom_keys(viewer, base):
    page = keyed(viewer, base)
    page.press("+")
    assert abs(transform(page)[2] - 1.25) < 1e-6
    page.press("-")
    assert abs(transform(page)[2] - 1.0) < 1e-6
    page.press("-")
    page.press("0")
    assert transform(page)[2] == 1


def test_the_cursor_ring_is_visible(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")
    assert page.evaluate(
        "return getComputedStyle(document.querySelector('.cd-dg-cursor > .cd-dg-ring')).stroke;"
    ) != "none"


def test_a_cursor_off_screen_pans_along(viewer, base):
    page = keyed(viewer, base)
    page.press("ArrowRight")
    page.wheel(*on_canvas(page), -3000)     # the drawing far below the window
    page.evaluate("document.querySelector('.cd-dg-cursor').focus(); return true;")
    page.press("ArrowDown")
    assert page.evaluate("""
      var pane = document.getElementById('cd-diagram').getBoundingClientRect();
      var r = document.querySelector('.cd-dg-cursor .cd-dg-frame').getBoundingClientRect();
      return r.top >= pane.top && r.bottom <= pane.bottom;
    """)


def test_the_help_shows_the_diagram_keys(viewer, base):
    page = at(viewer, base, "/diagram/cpacs/")
    page.click(*centre(page, "#cd-help"))
    assert page.evaluate("""
      var line = document.querySelector('#cd-hint .cd-hint-line[data-tab="diagram"]');
      return !!line && !line.hidden && line.textContent.indexOf('zoom') !== -1;
    """)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q -k "tab_stop or right_opens or down_ or left_closes or space or enter or zoom_keys or ring or off_screen or help"`
Expected: FAIL (arrow keys do nothing; no `diagram` hint line). `test_the_diagram_is_one_tab_stop` may already pass.

- [ ] **Step 3: Implement the keys** — in `mount`, before `render(null);` at the end, add:

```js
    /* ---- keyboard (0010, 0016-0021, in two dimensions) ---- */

    function isTarget(box) {
      return box.item.kind === "element" && box.item.selectable;
    }

    function parentElement(box) {
      var p = box.parent;
      while (p && p.item.kind !== "element") p = p.parent;
      return p;
    }

    // The boxes are in depth-first order, so the children of one element
    // stand in them top to bottom.
    function siblings(box) {
      var parent = parentElement(box);
      if (!parent) return [box];
      return current.boxes.filter(function (b) { return isTarget(b) && parentElement(b) === parent; });
    }

    function firstChild(box) {
      for (var i = 0; i < current.boxes.length; i++) {
        var b = current.boxes[i];
        if (isTarget(b) && parentElement(b) === box) return b;
      }
      return null;
    }

    // Siblings first; past the last of them, the nearest box of the same
    // column in that direction — the column is what the eye runs down.
    function vertical(box, step) {
      var list = siblings(box);
      var index = list.indexOf(box);
      if (list[index + step]) return list[index + step];
      var best = null;
      for (var i = 0; i < current.boxes.length; i++) {
        var b = current.boxes[i];
        if (b === box || !isTarget(b) || b.depth !== box.depth) continue;
        var ahead = step > 0 ? b.y > box.y : b.y < box.y;
        if (ahead && (!best || Math.abs(b.y - box.y) < Math.abs(best.y - box.y))) best = b;
      }
      return best;
    }

    function columnEnd(box, step) {
      var column = current.boxes.filter(function (b) { return isTarget(b) && b.depth === box.depth; });
      column.sort(function (a, b) { return a.y - b.y; });
      return step < 0 ? column[0] : column[column.length - 1];
    }

    function moveTo(target) {
      if (!target) return;
      cursorKey = target.item.key;
      draw();
      focus();
      reveal(target, false);
    }

    canvas.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      var box = byKey[cursorKey];
      if (!box) return;
      var item = box.item;
      switch (event.key) {
        case "ArrowDown": moveTo(vertical(box, 1)); break;
        case "ArrowUp": moveTo(vertical(box, -1)); break;
        case "ArrowRight":
          if (item.expandable && !open[item.key]) toggle(item);
          else moveTo(firstChild(box));
          break;
        case "ArrowLeft":
          if (item.expandable && open[item.key]) toggle(item);
          else moveTo(parentElement(box));
          break;
        case "Home": moveTo(columnEnd(box, -1)); break;
        case "End": moveTo(columnEnd(box, 1)); break;
        case " ": choose(item, false); break;
        case "Enter": choose(item, true); break;
        case "+": case "=": zoomBy(1.25); break;
        case "-": zoomBy(0.8); break;
        case "0": setScale(1); break;
        default: return;
      }
      event.preventDefault();
    });
```

- [ ] **Step 4: The legend** — in `viewer.js`, in `HINT_GROUPS` insert after the tree group (after the line `], "tree"],` that closes the first group):

```js
    // The diagram's keys, in the tree's words where the keys are the tree's.
    // Its way back leads to the diagram, not to the tree it replaced.
    ["", "key", [
      [["\u2191", "\u2193"], "move"],
      [["\u2192", "\u2190"], "open, close"],
      [["Space"], "details"],
      [["Enter"], "details, and go there"],
      [["+", "\u2212", "0"], "zoom"],
      [["Esc", "Backspace"], "back to the diagram"]
    ], "diagram"],
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q`
Expected: 28 passed

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed

---

### Task 8: Theme, real schema, documentation

**Files:**
- Test: `tests/test_viewer_diagram_view.py`
- Create: `planning/decisions/0027-the-diagram-is-a-second-view.md`
- Modify: `planning/specs/CPACS_Documentation_System_Specification.md` (§3.3, §4.4, §7.4), `README.md` (section 2, `serve`)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the theme test** — append to `tests/test_viewer_diagram_view.py`

```python
# ---- theme ----

def contrast(a: str, b: str) -> float:
    """WCAG 2.1 contrast between two opaque `rgb()` strings."""
    def luminance(colour):
        parts = colour[colour.index("(") + 1:colour.index(")")].replace(",", " ").split()
        out = []
        for value in [float(v) / 255.0 for v in parts[:3]]:
            out.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_drawing_reads_in_both_themes(viewer, base, theme):
    page = at(viewer, base, "/diagram/cpacs/")
    colours = page.evaluate(f"""
      document.documentElement.setAttribute('data-theme', '{theme}');
      var header = document.querySelector('.cd-dg-item[data-path="header"]');
      return {{
        page: getComputedStyle(document.body).backgroundColor,
        name: getComputedStyle(header.querySelector('.cd-dg-name')).fill,
        frame: getComputedStyle(header.querySelector('.cd-dg-frame')).stroke,
        link: getComputedStyle(header.querySelector('.cd-dg-type-text')).fill
      }};
    """)
    page.evaluate("document.documentElement.removeAttribute('data-theme'); return true;")
    assert contrast(colours["name"], colours["page"]) >= 4.5
    assert contrast(colours["link"], colours["page"]) >= 4.5
    assert contrast(colours["frame"], colours["page"]) >= 3
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_viewer_diagram_view.py -q -k themes`
Expected: 2 passed (the styles from Task 4 already use the tokens). If one fails, the token chosen for that part is too faint in that theme: take the next stronger one (`--ink-soft` → `--ink`, `--rule-strong` → `--ink-soft`) in the diagram block of `styles.css`, never a literal colour.

- [ ] **Step 3: Check against the real schema** (Review Focus 3; a measurement, not a test)

```bash
uv run cpacs-doc build ../CPACS/schema/cpacs_schema.xsd -o "$TEMP/cd-real" --single
```

Then open `$TEMP/cd-real/cpacs-doc.html#/diagram/cpacs/vehicles/aircraft/model/wings/wing/` in the browser and, through `tests/cdp.py` or the DevTools console, time a full expansion of `wing`:

```js
var t = performance.now();
var item = document.querySelector('.cd-dg-item[data-path="vehicles/aircraft/model/wings/wing"]');
item.querySelector('.cd-dg-expander').dispatchEvent(new MouseEvent('click', {bubbles: true}));
performance.now() - t;
```

Expected: well under 100 ms per expand, the page responsive. Record the number in the final report. If it is not, profile `render` before changing anything (the text-width cache is the first suspect).

- [ ] **Step 4: Decision record** — create `planning/decisions/0027-the-diagram-is-a-second-view.md`

```markdown
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
- Every element box names its type, and the name opens the type's
  documentation beside the drawing (a modified click opens the type page).

## Rationale

A second route rather than a toggle keeps an address for every picture, which
is what the tree's addresses were made for (D4). Hand-written SVG rather than a
layout library: the layout is a tidy tree of a few hundred visible boxes, and
the line against libraries (N14) is the same one the viewer and the tests hold.
The overlay rather than the splitter: a diagram grows wide, and the column the
tree gives up is the width the drawing needs.

Not done here: links between the views from the panel and the type pages,
search inside the diagram, SVG export (F15, F16). The renderer draws into one
coordinate system, so export can follow without a second drawing path.
```

- [ ] **Step 5: Specification and README**

In `planning/specs/CPACS_Documentation_System_Specification.md`:

§3.3, after the two bullets add:

```markdown
A second layout draws the same tree as a diagram in the manner of XSDDiagram,
with the detail panel as an overlay (F19, decision 0027).
```

§4.4, in the code block after the `/tree/` line add:

```
/v3.5.1/diagram/vehicles/aircraft/model/                    → resolved via 404.html
```

§7.4, after F16 add:

```markdown
- **F19** Diagram view: the instance tree drawn left to right as XSDDiagram draws it — element boxes marked optional and repeated, compositors as symbols, children expanded on demand, every box naming and linking its type — under `/diagram/<path>/`, with zoom, pan and keyboard control. See `planning/specs/2026-09-30-diagram-view-design.md` and decision 0027.
```

In `README.md`, section 2, at the end of the `serve` subsection (after "Stop it with Ctrl-C." paragraph and the one following it), add:

```markdown
**The diagram.** Every tree address has a twin under `/diagram/`
(<http://127.0.0.1:8000/diagram/cpacs/>, or the *Diagram* tab): the same tree
drawn left to right the way XSDDiagram draws it. Click a box for its
documentation, its type name for the type's; `+`/`−` on a box expands it.
Ctrl+wheel zooms, dragging the canvas pans, and the keys are listed under `?`.
```

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -q`
Expected: all passed; report the count (303 before this work).

- [ ] **Step 7: Look at it**

Run `uv run cpacs-doc serve ../CPACS/schema/cpacs_schema.xsd`, open `http://127.0.0.1:8000/diagram/cpacs/vehicles/`, and compare the picture with XSDDiagram (`D:\Entwicklung\Docs\XSDDiagram\XSDDiagram.exe` on the same schema) in both themes. Report differences that are not intentional (the spec lists the intentional ones: aligned columns, type line).
