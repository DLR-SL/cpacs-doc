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
