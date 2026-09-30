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
