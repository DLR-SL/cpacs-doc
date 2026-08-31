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

# The strip is in the static markup now, so its presence says nothing: what
# these tests wait for is `setupTabs()`, which runs once the model has
# arrived and is what unhides the Handbook tab on a schema with sections.
READY = "return !document.getElementById('cd-tab-docs').hidden;"

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
  var tabs = ['cd-tab-tree', 'cd-tab-docs', 'cd-tab-search'];
  var shown = tabs.filter(function (id) { return !document.getElementById(id).hidden; });
  return {
    searchShown: !document.getElementById('cd-search-panel').hidden,
    docsShown: !document.getElementById('cd-docs').hidden,
    treeShown: !document.getElementById('cd-tree').hidden,
    stripShown: !document.getElementById('cd-tabs').hidden,
    head: !!document.querySelector('#cd-results .cd-pane-head'),
    query: document.getElementById('cd-search').value,
    rows: document.querySelectorAll('#cd-results .cd-result').length,
    onTab: document.getElementById('cd-tab-count').textContent,
    marked: shown.map(function (id) {
      return document.getElementById(id).getAttribute('aria-selected');
    }),
    stops: shown.map(function (id) { return document.getElementById(id).tabIndex; })
  };
"""


def search(page, text):
    click(page, "#cd-tab-search")
    page.evaluate(
        "var field = document.getElementById('cd-search');"
        "field.value = '" + text + "';"
        "field.dispatchEvent(new Event('input', {bubbles: true}));"
        "return true;"
    )
    page.wait_for(
        "return document.querySelectorAll('#cd-results .cd-result').length > 0;",
        "the results",
    )


def test_the_search_is_a_tab_and_the_strip_never_leaves(page):
    """The results looked laid over the tree because the strip stood above them
    marking neither half and putting both of its own out of the tab order. Search
    is a place of its own now, so the strip stays and marks it."""
    search(page, "he")
    shown = page.evaluate(STRIP)
    assert shown["searchShown"] and shown["stripShown"]
    assert not shown["treeShown"] and not shown["docsShown"]
    # A tab names the region, so a head under it would be the second label for
    # one thing.
    assert not shown["head"]
    # Exactly one marked tab and exactly one tab stop, at every moment.
    assert shown["marked"] == ["false", "false", "true"]
    assert shown["stops"] == [-1, -1, 0]


def test_the_field_stands_in_its_own_tab_and_nowhere_else(page):
    """A class that sets `display` outweighs the browser's own `[hidden]` rule,
    so `hidden` alone left the field standing under the tree as well. And the
    panel must not clip: the field's focus ring reaches past its own box."""
    shown = page.evaluate(
        "var panel = document.getElementById('cd-search-panel');"
        "var field = document.getElementById('cd-search').getBoundingClientRect();"
        "return { display: getComputedStyle(panel).display,"
        " overflow: getComputedStyle(panel).overflow,"
        " visible: field.width > 0 && field.height > 0 };"
    )
    assert shown["display"] == "none" and not shown["visible"]

    click(page, "#cd-tab-search")
    open_now = page.evaluate(
        "var panel = document.getElementById('cd-search-panel');"
        "var field = document.getElementById('cd-search').getBoundingClientRect();"
        "return { display: getComputedStyle(panel).display,"
        " overflow: getComputedStyle(panel).overflow,"
        " visible: field.width > 0 && field.height > 0 };"
    )
    assert open_now["display"] == "flex" and open_now["visible"]
    assert open_now["overflow"] == "visible"


def test_opening_a_result_keeps_the_query_for_coming_back_to(page):
    """Sixty hits are worth going through one at a time, so the click that opens
    one leaves the tab holding the field, the rows and the count."""
    search(page, "he")
    before = page.evaluate(STRIP)
    assert before["rows"] > 1

    click(page, "#cd-results .cd-result")
    after = page.evaluate(STRIP)
    assert after["treeShown"] and not after["searchShown"]
    assert after["marked"] == ["true", "false", "false"]
    assert after["query"] == "he" and after["rows"] == before["rows"]
    # And the tab says so while the field is off screen.
    assert after["onTab"] == str(before["rows"])

    click(page, "#cd-tab-search")
    assert page.evaluate(STRIP)["rows"] == before["rows"]


def test_escape_is_the_one_thing_that_gives_the_query_up(page):
    search(page, "he")
    page.press("Escape")
    page.wait_for(
        "return document.querySelectorAll('#cd-results .cd-result').length === 0;",
        "the results to clear",
    )
    back = page.evaluate(STRIP)
    assert back["treeShown"] and back["query"] == "" and back["onTab"] == ""


def visible_groups(page):
    return page.evaluate("""
      return Array.from(document.querySelectorAll('#cd-hint .cd-hint-line'))
        .filter(function (line) { return line.getClientRects().length > 0; })
        .map(function (line) { return line.querySelector('.cd-hint-lead').textContent; });
    """)


def test_the_question_mark_strip_carries_the_query_forms_too(page):
    """The forms were a `title` on the field and a note only an already-narrowing
    reader ever saw. They belong where someone looks for them — which is the
    `?` while standing in Search, the tab they are about."""
    click(page, "#cd-help")
    page.wait_for("return !!document.getElementById('cd-hint');", "the hint")
    click(page, "#cd-tab-search")
    assert visible_groups(page) == ["Search"]
    forms = page.evaluate("""
      return Array.from(document.querySelectorAll(
        '#cd-hint .cd-hint-line[data-tab="search"] .cd-hint-form'))
        .map(function (n) { return n.textContent; });
    """)
    assert "type:" in forms and "@" in forms
    # A form is typed, a key is pressed: only the keys are set in relief, and
    # the keys belong to the tree.
    click(page, "#cd-tab-tree")
    assert visible_groups(page) == ["Tree"]
    assert page.evaluate("""
      return document.querySelectorAll(
        '#cd-hint .cd-hint-line[data-tab="tree"] kbd').length;
    """) == 7


def test_the_handbook_offers_no_hint_and_says_so_on_the_button(page):
    """The Handbook is read, not driven: there are no keys to tell anyone
    about. Rather than an empty box or the keys of a place the reader is not
    in, the hint stays away and the `?` is plainly not on offer."""
    click(page, "#cd-help")
    page.wait_for("return !!document.getElementById('cd-hint');", "the hint")

    click(page, "#cd-tab-docs")
    assert visible_groups(page) == []
    help_state = page.evaluate("""
      var help = document.getElementById('cd-help');
      return {
        disabled: help.disabled,
        expanded: help.getAttribute('aria-expanded'),
        dim: parseFloat(getComputedStyle(help).opacity)
      };
    """)
    assert help_state["disabled"] is True, help_state
    assert help_state["expanded"] == "false", help_state
    # Dimmed, not gone: a button that leaves the strip is harder to place.
    assert 0 < help_state["dim"] < 0.7, help_state

    # The strip keeps its own gap where the hint is not showing, or the pane
    # would butt against the tabs on the strength of a box that is not there.
    gap = page.evaluate("""
      var strip = document.getElementById('cd-tabs').getBoundingClientRect();
      return document.getElementById('cd-docs').getBoundingClientRect().top - strip.bottom;
    """)
    assert gap > 4, gap

    # Suppressed, not closed — leaving the Handbook gives back what was open.
    click(page, "#cd-tab-tree")
    assert visible_groups(page) == ["Tree"]
    assert page.evaluate("return document.getElementById('cd-help').disabled;") is False


def test_a_schema_without_sections_shows_the_other_two_tabs(browser, tmp_path_factory):
    """One half is not a choice, so the Handbook tab stays away — but Tree and
    Search name each other whatever the schema carries."""
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
        assert not browser.evaluate("return document.getElementById('cd-tabs').hidden;")
        assert browser.evaluate("return document.getElementById('cd-tab-docs').hidden;")
        assert browser.evaluate(
            "return getComputedStyle(document.getElementById('cd-tab-docs')).display;"
        ) == "none"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
