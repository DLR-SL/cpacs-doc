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


def test_the_diagram_keeps_its_height_in_a_narrow_window(viewer, base):
    """The narrow layout lets the panes size themselves; the diagram has no
    content height, so it needs one of its own, and the overlay must fit."""
    viewer.command("Emulation.setDeviceMetricsOverride", {
        "width": 600, "height": 800, "deviceScaleFactor": 1, "mobile": False})
    try:
        page = at(viewer, base, "/diagram/cpacs/header/")
        height = page.evaluate(
            "return document.getElementById('cd-diagram').getBoundingClientRect().height;")
        width = page.evaluate(
            "return document.getElementById('cd-detail').getBoundingClientRect().width"
            " <= window.innerWidth;")
        assert height > 300
        assert width
    finally:
        viewer.command("Emulation.clearDeviceMetricsOverride")


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
