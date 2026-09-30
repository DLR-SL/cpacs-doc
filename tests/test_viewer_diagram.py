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
      return { key: b.item.key, kind: b.item.kind, name: b.item.name || b.item.compositor, depth: b.depth,
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


def _lone_groups(boxes):
    by_key = {b["key"]: b for b in boxes}
    parent = {c: b["key"] for b in boxes for c in b["children"]}
    lone = {
        b["key"] for b in boxes
        if b["key"] in parent and b["kind"] == "group"
        and len(by_key[parent[b["key"]]]["children"]) == 1
    }
    return by_key, parent, lone


def test_a_box_stands_at_the_top_of_its_subtree(page):
    """XSDDiagram's Top alignment: a box is not centred on its children."""
    boxes = laid_out(page)["boxes"]
    by_key, _, lone = _lone_groups(boxes)

    def subtree(box):
        yield box
        for key in box["children"]:
            yield from subtree(by_key[key])

    checked = 0
    for box in boxes:
        if not box["children"] or box["key"] in lone:
            continue
        checked += 1
        least = min(b["y"] for b in subtree(box))
        assert abs(box["y"] - least) < 0.5, box["name"]
    assert checked > 3


def test_a_lone_compositor_lines_up_with_its_parent(page):
    """As in XSDDiagram: the connector to a compositor that is the only child
    runs straight."""
    boxes = laid_out(page)["boxes"]
    by_key, parent, lone = _lone_groups(boxes)
    assert lone
    for key in lone:
        group, owner = by_key[key], by_key[parent[key]]
        assert abs((group["y"] + group["h"] / 2) - (owner["y"] + owner["h"] / 2)) < 0.5


def test_children_start_right_of_their_own_parent(page):
    """As in XSDDiagram: the children of a box share one x, just past that
    box and its gap — not past the widest box of the whole depth."""
    boxes = laid_out(page)["boxes"]
    by_key = {b["key"]: b for b in boxes}
    checked = 0
    for box in boxes:
        if not box["children"]:
            continue
        xs = {by_key[k]["x"] for k in box["children"]}
        assert len(xs) == 1, box["name"]
        assert xs.pop() == box["x"] + box["w"] + 20, box["name"]
        checked += 1
    assert checked > 3


def test_a_long_name_widens_only_its_own_branch(page):
    """alpha and wing stand at the same depth under parents of different
    width; each column follows its own parent."""
    boxes = laid_out(page)["boxes"]
    alpha = next(b for b in boxes if b["name"] == "alpha")
    wing = next(b for b in boxes if b["name"] == "wing")
    assert alpha["depth"] == wing["depth"]
    assert alpha["x"] != wing["x"]


def test_the_drawing_holds_every_box(page):
    result = laid_out(page)
    for box in result["boxes"]:
        assert box["x"] >= 0 and box["y"] >= 0
        assert box["x"] + box["w"] <= result["width"]
        assert box["y"] + box["h"] <= result["height"]

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
    covered: function () { return 0; },
    expert: EXPERT,
    rememberExpert: function (on) { dgCalls.push(['expert', on]); },
    rememberPath: function (on) { dgCalls.push(['path', on]); }
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
    """Expert view: every type line and every bound, which most of the tests
    below are about."""
    run(page, MOUNT.replace("EXPERT", "true"))
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
        headerCard: (header.querySelector('.cd-dg-card') || {}).textContent
      };
    """)
    assert result["wingsOptional"] and result["dash"] != "none"
    assert result["headerDash"] == "none"
    assert result["repeated"] and result["shadow"]
    assert result["card"] == "1..\u221e"
    assert result["headerCard"] == "1..1"  # the expert view writes every bound


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


# ---- the route ----

def test_the_route_to_the_selection_is_marked(mounted):
    """The way an instance takes from the root to the chosen element: the
    boxes on it and the lines between them, and nothing else."""
    assert mounted.evaluate("""
      var before = document.querySelector('#dg-host .cd-dg-trail-link').getAttribute('d');
      dg.show(['wings', 'wing', 'uID'], false);
      var on = Array.prototype.map.call(
        document.querySelectorAll('#dg-host .cd-dg-element.cd-dg-on-trail'),
        function (g) { return g.getAttribute('data-path'); });
      return [before, on,
              document.querySelectorAll('#dg-host .cd-dg-group.cd-dg-on-trail').length,
              document.querySelector('#dg-host .cd-dg-trail-link').getAttribute('d').length > 0,
              dgItem('header').classList.contains('cd-dg-on-trail'),
              dgItem('wings/wing/uID').classList.contains('cd-dg-on-trail')];
    """) == ["", ["", "wings", "wings/wing"], 3, True, False, False]


def test_hovering_a_box_previews_its_route(mounted):
    assert mounted.evaluate("""
      var before = document.querySelector('#dg-host .cd-dg-hover-link').getAttribute('d');
      dgItem('extras').querySelector('.cd-dg-frame')
        .dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      var during = document.querySelector('#dg-host .cd-dg-hover-link').getAttribute('d');
      var marked = dgItem('extras').classList.contains('cd-dg-hover-trail')
        && dgItem('').classList.contains('cd-dg-hover-trail')
        && !dgItem('header').classList.contains('cd-dg-hover-trail');
      document.querySelector('#dg-host .cd-dg-svg').dispatchEvent(new MouseEvent('mouseleave'));
      return [before, during.length > 0, marked,
              document.querySelector('#dg-host .cd-dg-hover-link').getAttribute('d'),
              document.querySelectorAll('#dg-host .cd-dg-hover-trail').length];
    """) == ["", True, True, "", 0]


# ---- expert view ----

@pytest.fixture
def plain(page):
    """The default: names only, and only the bounds the frame does not say."""
    run(page, MOUNT.replace("EXPERT", "false"))
    page.evaluate(HELPERS)
    return page


CARDS = """
  dg.show(['wings', 'wing', 'uID'], false);
  function card(path) {
    var c = dgItem(path).querySelector('.cd-dg-card');
    return c ? c.textContent : null;
  }
  return {
    header: card('header'), wings: card('wings'), wing: card('wings/wing'),
    uid: card('wings/wing/uID'),
    types: document.querySelectorAll('#dg-host .cd-dg-type-text').length,
    headerHeight: dgItem('header').querySelector('.cd-dg-frame').getBBox().height
  };
"""


def test_the_default_shows_names_and_only_the_bounds_the_frame_does_not(plain):
    """0..1 is what the dashes say and 1..1 what a plain frame says; 1..∞ is
    news, the stacked frame only hints at it."""
    assert plain.evaluate(CARDS) == {
        "header": None, "wings": None, "wing": "1..∞", "uid": None,
        "types": 0, "headerHeight": 22,
    }


def test_the_expert_view_shows_every_type_and_every_bound(mounted):
    assert mounted.evaluate(CARDS) == {
        "header": "1..1", "wings": "0..1", "wing": "1..∞", "uid": "1..1",
        "types": 6, "headerHeight": 34,
    }


def test_the_expert_toggle_switches_in_place_and_is_remembered(plain):
    result = plain.evaluate("""
      dg.show(['wings'], false);
      var button = document.getElementById('cd-dg-expert');
      var pressed = button.getAttribute('aria-pressed');
      var before = dgItem('wings').querySelector('.cd-dg-frame').getBoundingClientRect();
      button.click();
      var after = dgItem('wings').querySelector('.cd-dg-frame').getBoundingClientRect();
      return {
        before: pressed, after: button.getAttribute('aria-pressed'),
        types: document.querySelectorAll('#dg-host .cd-dg-type-text').length > 0,
        moved: Math.abs(after.left - before.left) + Math.abs(after.top - before.top),
        calls: dgCalls.filter(function (c) { return c[0] === 'expert'; }),
        selected: dgItem('wings').classList.contains('cd-dg-selected')
      };
    """)
    assert result["before"] == "false" and result["after"] == "true"
    assert result["types"] is True
    assert result["moved"] < 0.5
    assert result["calls"] == [["expert", True]]
    assert result["selected"] is True


# ---- touch targets and symbols ----

def test_the_expander_is_easy_to_hit(mounted):
    """Ten pixels drawn, twenty-four to hit."""
    size = mounted.evaluate(
        "var b = dgItem('wings').querySelector('.cd-dg-expander').getBBox();"
        " return [b.width, b.height];"
    )
    assert size[0] >= 24 and size[1] >= 24


def test_compositor_symbols_are_legible(mounted):
    size = mounted.evaluate(
        "var b = document.querySelector('#dg-host .cd-dg-group .cd-dg-frame').getBBox();"
        " return [b.width, b.height];"
    )
    assert size[0] >= 36 and size[1] >= 18


# ---- vertical rhythm ----

GAPS = """
  function rect(path) { return dgItem(path).querySelector('.cd-dg-frame').getBoundingClientRect(); }
  var card = dgItem('header').querySelector('.cd-dg-card');
  return { gap: rect('wings').top - rect('header').bottom,
           cardClear: card ? rect('wings').top - card.getBoundingClientRect().bottom : null };
"""


def test_rows_without_a_bound_sit_close(plain):
    """Room under a box is kept only for what stands there: a bound, or the
    stacked frame of a repeated element."""
    assert plain.evaluate(GAPS)["gap"] <= 10


def test_a_bound_never_runs_into_the_next_box(mounted):
    gaps = mounted.evaluate(GAPS)
    assert gaps["cardClear"] is not None and gaps["cardClear"] >= 2


# ---- the path switch ----

def test_the_path_can_be_switched_off_and_back_on(mounted):
    """Off takes the path's line, its coloured frames and the preview away;
    the chosen box keeps its mark, since the selection has to stay visible."""
    result = mounted.evaluate("""
      dg.show(['wings', 'wing', 'uID'], false);
      var button = document.getElementById('cd-dg-path');
      var before = button.getAttribute('aria-pressed');
      button.click();
      var off = {
        pressed: button.getAttribute('aria-pressed'),
        line: document.querySelector('#dg-host .cd-dg-trail-link').getAttribute('d'),
        frames: document.querySelectorAll('#dg-host .cd-dg-on-trail').length,
        selected: dgItem('wings/wing/uID').classList.contains('cd-dg-selected')
      };
      dgItem('extras').querySelector('.cd-dg-frame')
        .dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
      off.preview = document.querySelector('#dg-host .cd-dg-hover-link').getAttribute('d');
      button.click();
      return { before: before, off: off,
               on: document.querySelectorAll('#dg-host .cd-dg-on-trail').length,
               calls: dgCalls.filter(function (c) { return c[0] === 'path'; }) };
    """)
    assert result["before"] == "true"
    assert result["off"] == {"pressed": "false", "line": "", "frames": 0,
                             "selected": True, "preview": ""}
    assert result["on"] > 0
    assert result["calls"] == [["path", False], ["path", True]]
