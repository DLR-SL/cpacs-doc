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
    """XSDDiagram's Top alignment: a box is not centered on its children."""
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
    deselect: function () { dgCalls.push(['deselect']); }
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


# ---- clearing the selection ----

BACKGROUND = """
  var svg = document.querySelector('#dg-host .cd-dg-svg');
  var r = svg.getBoundingClientRect();
  function fire(type, x, y) {
    var init = { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0, pointerId: 1 };
    svg.dispatchEvent(type.indexOf('pointer') === 0 ? new PointerEvent(type, init) : new MouseEvent(type, init));
  }
"""


def test_a_click_on_empty_canvas_clears_the_selection(mounted):
    """As in XSDDiagram: the free canvas takes the mark and the path away."""
    assert mounted.evaluate(BACKGROUND + """
      dg.show(['wings', 'wing'], false);
      var x = r.right - 20, y = r.bottom - 20;
      fire('pointerdown', x, y); fire('pointerup', x, y); fire('click', x, y);
      return [document.querySelectorAll('#dg-host .cd-dg-selected').length,
              document.querySelectorAll('#dg-host .cd-dg-on-trail').length,
              dgCalls];
    """) == [0, 0, [["deselect"]]]


def test_panning_does_not_clear_the_selection(mounted):
    """A drag ends in a click on the canvas too; that one is the end of a
    pan, not a wish to deselect."""
    assert mounted.evaluate(BACKGROUND + """
      dg.show(['wings', 'wing'], false);
      var x = r.right - 20, y = r.bottom - 20;
      fire('pointerdown', x, y); fire('pointermove', x - 40, y - 30);
      fire('pointerup', x - 40, y - 30); fire('click', x - 40, y - 30);
      return [dgItem('wings/wing').classList.contains('cd-dg-selected'), dgCalls];
    """) == [True, []]


# ---- export ----

SVG_EXPORT = """
  var markup = dg.exportSvg();
  var doc = new DOMParser().parseFromString(markup, 'image/svg+xml');
  var root = doc.documentElement;
  var view = doc.querySelector('.cd-dg-view');
  var frame = doc.querySelector('.cd-dg-frame');
  return { tag: root.nodeName, ns: root.namespaceURI,
           width: +root.getAttribute('width'), height: +root.getAttribute('height'),
           customProperties: markup.indexOf('var(--') !== -1,
           names: markup.indexOf('>wings<') !== -1,
           probe: !!doc.querySelector('.cd-dg-probe'),
           rings: doc.querySelectorAll('.cd-dg-ring, .cd-dg-hit').length,
           transform: view ? view.getAttribute('transform') : null,
           styled: /fill:/.test(frame.getAttribute('style') || '') };
"""


def test_the_drawing_exports_as_a_self_contained_svg(mounted):
    """The file carries its own styles — the page's custom properties do not
    travel with it — and none of the page's machinery: probe, focus rings,
    hit areas."""
    first = mounted.evaluate("dg.show(['wings', 'wing'], false);" + SVG_EXPORT)
    assert first["tag"] == "svg" and first["ns"] == "http://www.w3.org/2000/svg"
    assert first["width"] > 100 and first["height"] > 100
    assert first["customProperties"] is False
    assert first["names"] is True
    assert first["probe"] is False and first["rings"] == 0
    assert first["transform"] == "translate(24 24)"
    assert first["styled"] is True


def test_the_export_does_not_depend_on_zoom_or_pan(mounted):
    before = mounted.evaluate(SVG_EXPORT)
    mounted.evaluate("document.getElementById('cd-dg-zoom-in').click(); return true;")
    after = mounted.evaluate(SVG_EXPORT)
    assert (after["width"], after["height"], after["transform"]) == \
        (before["width"], before["height"], before["transform"])


def test_the_drawing_exports_as_a_png(mounted):
    assert mounted.evaluate(
        "return dg.exportPng().then(function (blob) { return [blob.type, blob.size > 1000]; });"
    ) == ["image/png", True]


def test_the_export_is_named_after_the_selection(mounted):
    assert mounted.evaluate("""
      var bare = dg.exportName();
      dg.show(['wings', 'wing'], false);
      return [bare, dg.exportName()];
    """) == ["cpacs", "cpacs-wings-wing"]


def test_the_svg_has_a_transparent_ground(mounted):
    """Nothing stands between the root and the drawing: no rectangle of the
    viewer's colour behind it."""
    assert mounted.evaluate("""
      var doc = new DOMParser().parseFromString(dg.exportSvg(), 'image/svg+xml');
      var root = doc.documentElement;
      return [root.children.length, root.firstElementChild.getAttribute('class')];
    """) == [1, "cd-dg-view"]


def test_the_png_has_a_transparent_ground(mounted):
    """Only the ground is left out: the boxes keep their fill, so names stay
    readable on whatever the picture is placed on."""
    assert mounted.evaluate("""
      return dg.exportPng().then(function (blob) {
        return createImageBitmap(blob).then(function (bitmap) {
          var canvas = document.createElement('canvas');
          canvas.width = bitmap.width; canvas.height = bitmap.height;
          var context = canvas.getContext('2d');
          context.drawImage(bitmap, 0, 0);
          var corner = context.getImageData(1, 1, 1, 1).data[3];
          // The root box starts at the margin (24 px, twice that in the PNG).
          var box = context.getImageData(24 * 2 + 12, 24 * 2 + 6, 1, 1).data[3];
          return [corner, box];
        });
      });
    """) == [0, 255]
