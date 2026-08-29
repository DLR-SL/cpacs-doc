"""The documentation pane, in a browser.

The general documentation takes the tree's place in the same slot, as the
search results do. What that costs is a mode the reader can get stuck in, so
what is tested here is mostly the way back out.
"""

from __future__ import annotations

import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import cdp

from cpacs_doc import serve as serve_module

FIXTURES = Path(__file__).parent / "fixtures"

SCHEMA = "handbook.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = "return !document.getElementById('cd-tabs').hidden;"

STATE = """
  var docs = document.getElementById('cd-docs');
  var tree = document.getElementById('cd-tree');
  var tab = document.getElementById('cd-tab-docs');
  var entries = docs.querySelectorAll('.cd-result');
  var titles = [];
  for (var i = 0; i < entries.length; i++) titles.push(entries[i].textContent);
  return {
    docsShown: !docs.hidden,
    treeShown: !tree.hidden,
    current: tab.getAttribute('aria-selected'),
    treeCurrent: document.getElementById('cd-tab-tree').getAttribute('aria-selected'),
    titles: titles,
    selected: docs.querySelector('.cd-result.cd-selected')
      ? docs.querySelector('.cd-result.cd-selected').textContent : null,
    heading: document.querySelector('#cd-detail h1')
      ? document.querySelector('#cd-detail h1').textContent : null,
    detail: document.getElementById('cd-detail').textContent,
    citable: document.querySelector('#cd-detail .cd-kind a')
      ? document.querySelector('#cd-detail .cd-kind a').getAttribute('href') : null
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the documentation toggle")
    browser.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )
    return browser


def state(page) -> dict:
    return page.evaluate(STATE)


def click(page, selector):
    spot = page.evaluate(
        "var box = document.querySelector('" + selector + "').getBoundingClientRect();"
        "return { x: box.left + box.width / 2, y: box.top + box.height / 2 };"
    )
    page.click(spot["x"], spot["y"])


def test_the_tab_puts_the_handbook_where_the_tree_was(page):
    before = state(page)
    assert before["treeShown"] and not before["docsShown"]
    click(page, "#cd-tab-docs")
    after = state(page)
    assert after["docsShown"] and not after["treeShown"]
    assert after["current"] == "true"


def test_the_list_is_the_documents_own_table_of_contents(page):
    """Document order, titles as written. A section without a title is not in
    the list because it has no name to be listed under."""
    click(page, "#cd-tab-docs")
    assert state(page)["titles"] == ["1. Overview", "2. Coordinate Systems", "Units", "units"]


def test_a_section_opens_in_the_detail_panel_and_names_its_page(page):
    click(page, "#cd-tab-docs")
    click(page, "#cd-docs .cd-result:nth-child(2)")
    shown = state(page)
    assert shown["heading"] == "2. Coordinate Systems"
    assert "Where the axes point." in shown["detail"]
    assert shown["citable"].endswith("/doc/2-coordinate-systems/index.html")
    # The list stays open and marks where the reader is, so the next chapter is
    # one click away.
    assert shown["docsShown"]
    assert shown["selected"] == "2. Coordinate Systems"


def test_the_citable_page_the_panel_names_actually_answers(page, base):
    """`serve` reproduces the deployment target, so a link the viewer offers
    has to resolve there as well."""
    click(page, "#cd-tab-docs")
    click(page, "#cd-docs .cd-result:nth-child(2)")
    href = state(page)["citable"]
    with urllib.request.urlopen(base + href) as answer:
        assert answer.status == 200
        body = answer.read().decode("utf-8")
    assert "<h1>2. Coordinate Systems</h1>" in body
    assert "Where the axes point." in body


def test_the_other_tab_and_escape_both_lead_back_to_the_tree(page):
    click(page, "#cd-tab-docs")
    click(page, "#cd-tab-tree")
    back = state(page)
    assert back["treeShown"] and back["treeCurrent"] == "true"

    click(page, "#cd-tab-docs")
    assert state(page)["docsShown"]
    page.press("Escape")
    back = state(page)
    assert back["treeShown"] and not back["docsShown"]
    assert back["current"] == "false"


def test_selecting_a_node_leaves_the_documentation_behind(page):
    """The panel shows one thing at a time, and the tree is what the reader
    came back for."""
    click(page, "#cd-tab-docs")
    click(page, "#cd-docs .cd-result:nth-child(1)")
    assert state(page)["heading"] == "1. Overview"
    page.press("Escape")
    page.press("ArrowDown")
    page.press(" ")
    assert state(page)["heading"] == "header"


def test_the_arrow_keys_walk_the_list(page):
    click(page, "#cd-tab-docs")
    page.evaluate("document.querySelector('#cd-docs .cd-result').focus(); return true;")
    page.press("ArrowDown")
    assert page.evaluate("return document.activeElement.textContent;") == "2. Coordinate Systems"
    page.press("ArrowUp")
    assert page.evaluate("return document.activeElement.textContent;") == "1. Overview"


STRIP = """
  var head = document.querySelector('#cd-results .cd-pane-head');
  return {
    resultsShown: !document.getElementById('cd-results').hidden,
    docsShown: !document.getElementById('cd-docs').hidden,
    treeShown: !document.getElementById('cd-tree').hidden,
    tabsHidden: document.getElementById('cd-tabs').hidden,
    title: head ? head.querySelector('.cd-pane-title').textContent : null,
    back: head ? head.querySelector('.cd-pane-close').getAttribute('aria-label') : null,
    marked: [document.getElementById('cd-tab-tree').getAttribute('aria-selected'),
             document.getElementById('cd-tab-docs').getAttribute('aria-selected')],
    stops: [document.getElementById('cd-tab-tree').tabIndex,
            document.getElementById('cd-tab-docs').tabIndex]
  };
"""


def search(page, text):
    page.evaluate(
        "var field = document.getElementById('cd-search');"
        "field.value = '" + text + "';"
        "field.dispatchEvent(new Event('input', {bubbles: true}));"
        "return true;"
    )
    page.wait_for("return !document.getElementById('cd-results').hidden;", "the results")


def test_the_results_take_the_strip_away_rather_than_unmarking_it(page):
    """The strip names the two halves of the documentation, and the results are
    neither. Standing above them it marked no tab at all and put both of its own
    out of the tab order, which reads as a layer covering the tree rather than as
    the swap it is. The results carry a head of their own instead."""
    search(page, "he")
    shown = page.evaluate(STRIP)
    assert shown["resultsShown"] and shown["tabsHidden"]
    assert shown["title"] == "Results"
    # Exactly one marked tab and exactly one tab stop at every moment, so the
    # strip is already right when it comes back.
    assert shown["marked"] == ["true", "false"]
    assert shown["stops"] == [0, -1]


def test_the_head_and_the_empty_field_both_lead_back_to_the_half_the_reader_left(page):
    """Not always the tree: whoever searched from the handbook is returned to
    it, and the head says so before it is pressed."""
    click(page, "#cd-tab-docs")
    search(page, "he")
    shown = page.evaluate(STRIP)
    assert shown["back"] == "Close the results and go back to the handbook"
    assert shown["marked"] == ["false", "true"]

    page.evaluate("document.querySelector('#cd-results .cd-pane-close').click(); return true;")
    back = page.evaluate(STRIP)
    assert back["docsShown"] and not back["treeShown"] and not back["tabsHidden"]

    # And the same for a field emptied rather than closed.
    search(page, "he")
    page.evaluate(
        "var field = document.getElementById('cd-search');"
        "field.value = 'h';"
        "field.dispatchEvent(new Event('input', {bubbles: true}));"
        "return true;"
    )
    page.wait_for("return document.getElementById('cd-results').hidden;", "the results to close")
    assert page.evaluate(STRIP)["docsShown"]


def test_a_schema_without_sections_shows_no_tabs(browser, tmp_path_factory):
    """One half is not a choice, and a strip naming only what is already on
    screen says nothing."""
    directory = tmp_path_factory.mktemp("plain")
    schema = directory / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=directory / "media", limit=0
    )
    assert site.rebuild()
    server = serve_module.create_server(site, "127.0.0.1", 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        browser.open(address + "/tree/cpacs/")
        browser.wait_for('return document.querySelectorAll(\'[role="treeitem"]\').length > 1;')
        assert browser.evaluate("return document.getElementById('cd-tabs').hidden;")
        assert browser.evaluate(
            "return getComputedStyle(document.getElementById('cd-tabs')).display;"
        ) == "none"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
