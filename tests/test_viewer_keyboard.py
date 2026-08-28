"""The viewer's keyboard behaviour, in a browser (F1, N13).

Everything here needs a real browser and nothing else does. The Python tests
see the shell the generator writes; a DOM stand-in sees the logic. Neither sees
a computed style, and a rule that hid the cursor while the arrow keys were
moving it went through both — hence this file.

The browser is shared by the module and each test navigates afresh: starting
one costs about a second, a navigation about a tenth of that.
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

import pytest

from cpacs_doc import serve as serve_module

import cdp

FIXTURES = Path(__file__).parent / "fixtures"

BROWSER = cdp.find_browser()
# Skipping quietly is right on a machine without a browser and wrong in CI,
# where it would let this whole file lapse unnoticed.
if BROWSER is None and os.environ.get("CPACS_DOC_REQUIRE_BROWSER"):
    raise RuntimeError(
        "CPACS_DOC_REQUIRE_BROWSER is set and no Chrome or Edge was found"
    )

pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

# What the page is asked for after every step. One round trip, so a test reads
# as a sequence of presses rather than as a sequence of queries.
STATE = """
  var rows = Array.prototype.slice.call(document.querySelectorAll('[role="treeitem"]'));
  var cursor = document.querySelector('.cd-node.cd-cursor');
  var active = document.activeElement;
  function label(row) {
    var name = row && row.querySelector('.cd-name');
    return name ? name.textContent : null;
  }
  var style = cursor ? getComputedStyle(cursor) : null;
  return {
    names: rows.map(label),
    cursor: label(cursor),
    outline: style ? style.outlineStyle + " " + style.outlineWidth : null,
    focusIsCursor: active === cursor,
    focus: active ? (active.id || active.className) : null,
    tabStops: rows.filter(function (row) { return row.tabIndex === 0; }).length,
    history: window.history.length,
    scrolled: window.scrollY
  };
"""


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """The viewer, served the way it is deployed (§3.4, R4)."""
    directory = tmp_path_factory.mktemp("site")
    schema = directory / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=directory / "media", limit=0
    )
    assert site.rebuild()
    server = serve_module.create_server(site, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


TREE_READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'


@pytest.fixture(scope="module")
def browser(tmp_path_factory, base):
    driver = cdp.Browser(BROWSER)
    driver.start(tmp_path_factory.mktemp("profile"))
    # The hint is shown to a reader who has not used the keys yet. Every test
    # but the ones about the hint itself wants the steady state, so it is
    # marked as seen once for this origin before anything else runs.
    assert cdp.reachable(base + "/tree/cpacs/"), "the development server did not answer"
    driver.open(base + "/tree/cpacs/")
    driver.wait_for(TREE_READY, "the tree")
    driver.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )
    yield driver
    driver.close()


@pytest.fixture
def page(browser, base):
    """A freshly loaded tree, with the keyboard already in it."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(TREE_READY, "the tree")
    # A reader arrives at the tree by clicking or by Tab; the tests start from
    # there rather than repeating the way in every one of them.
    browser.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    return browser


def state(page) -> dict:
    return page.evaluate(STATE)


def test_the_tree_is_a_single_tab_stop(page):
    """One tab stop for the whole tree, not two per row: the tree has 54,552
    nodes, and tabbing through them is not a way in."""
    assert state(page)["tabStops"] == 1


def test_the_cursor_is_drawn_while_it_holds_the_focus(page):
    """The row the keyboard points at is the row that has the focus, so a rule
    that suppresses the outline on focus takes the cursor with it. That is what
    happened, and nothing but a computed style catches it."""
    before = state(page)
    assert before["focusIsCursor"], f"focus on {before['focus']}"
    assert before["outline"] is not None
    assert "none" not in before["outline"], f"outline: {before['outline']}"


def test_the_arrow_keys_move_the_cursor_and_the_focus_with_it(page):
    start = state(page)
    page.press("ArrowDown")
    moved = state(page)
    assert moved["cursor"] != start["cursor"]
    assert moved["focusIsCursor"], f"focus on {moved['focus']}"
    assert "none" not in moved["outline"]
    page.press("ArrowUp")
    assert state(page)["cursor"] == start["cursor"]


def test_arrow_right_expands_and_the_focus_survives_the_rebuild(page):
    """Expanding replaces the whole tree in the DOM, focused row included."""
    page.press("ArrowDown")          # cpacs -> wings, which has children
    before = state(page)
    page.press("ArrowRight")
    after = state(page)
    assert len(after["names"]) > len(before["names"])
    assert after["cursor"] == before["cursor"]
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_arrow_right_steps_into_the_open_node_and_arrow_left_back_out(page):
    page.press("ArrowDown")
    page.press("ArrowRight")
    parent = state(page)["cursor"]
    page.press("ArrowRight")
    assert state(page)["cursor"] != parent
    page.press("ArrowLeft")
    assert state(page)["cursor"] == parent
    before = len(state(page)["names"])
    page.press("ArrowLeft")
    closed = state(page)
    assert len(closed["names"]) < before, "the parent should be closed"
    assert closed["cursor"] == parent


def test_home_and_end_reach_the_ends_of_what_is_visible(page):
    names = state(page)["names"]
    page.press("End")
    assert state(page)["cursor"] == names[-1]
    page.press("Home")
    assert state(page)["cursor"] == names[0]


def test_arrowing_writes_no_history_entry(page):
    """The cursor is not the selection. Were every arrow key to select, the
    back button would be spent after a few rows."""
    before = state(page)["history"]
    for _ in range(5):
        page.press("ArrowDown")
    assert state(page)["history"] == before


def test_the_arrow_keys_do_not_scroll_the_page_instead(page):
    for _ in range(5):
        page.press("ArrowDown")
    assert state(page)["scrolled"] == 0


def test_space_selects_without_leaving_the_tree(page):
    page.press("ArrowDown")
    before = state(page)["history"]
    page.press(" ")
    after = state(page)
    assert after["history"] == before + 1
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_enter_selects_and_hands_the_keyboard_to_the_detail_panel(page):
    page.press("ArrowDown")
    target = state(page)["cursor"]
    page.press("Enter")
    assert state(page)["focus"] == "cd-detail"
    shown = page.evaluate("return document.getElementById('cd-detail').textContent;")
    assert target in shown
    # The cursor keeps its mark while the keyboard is away, so the way back is
    # visible; Escape is that way back.
    assert state(page)["cursor"] == target
    page.press("Escape")
    assert state(page)["focusIsCursor"]


def test_the_keys_work_right_after_a_click(page):
    """A click leaves the focus on the button inside the row, not on the row.
    This is the way most readers reach the tree."""
    spot = page.evaluate("""
      var rows = document.querySelectorAll('[role="treeitem"]');
      var box = rows[rows.length - 1].querySelector('.cd-label').getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2,
               name: rows[rows.length - 1].querySelector('.cd-name').textContent };
    """)
    page.click(spot["x"], spot["y"])
    assert state(page)["cursor"] == spot["name"]
    page.press("ArrowUp")
    after = state(page)
    assert after["cursor"] != spot["name"]
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_an_arrow_key_reaches_the_tree_when_the_focus_is_nowhere(page):
    """Straight after a load the focus is nowhere. An arrow key would scroll a
    page that does not scroll — both panes carry their own scrollbar — so it is
    taken into the tree instead, which is what the reader meant."""
    page.evaluate("document.activeElement.blur(); return true;")
    assert page.evaluate("return document.activeElement === document.body;")
    page.press("ArrowDown")
    after = state(page)
    assert after["focusIsCursor"], f"focus on {after['focus']}"
    assert after["scrolled"] == 0


def test_one_tab_from_the_search_field_reaches_the_tree(page):
    page.evaluate("document.getElementById('cd-search').focus(); return true;")
    page.press("Tab")
    assert state(page)["focusIsCursor"], f"focus on {state(page)['focus']}"


def test_slash_opens_the_search_and_escape_returns_to_the_cursor(page):
    page.press("ArrowDown")
    cursor = state(page)["cursor"]
    page.press("/")
    assert page.evaluate("return document.activeElement.id;") == "cd-search"
    page.press("Escape")
    after = state(page)
    assert after["focusIsCursor"], f"focus on {after['focus']}"
    assert after["cursor"] == cursor


@pytest.fixture
def unseen(page, base):
    """The page as a first-time reader gets it, hint and all."""
    page.evaluate("window.localStorage.removeItem('cpacs-doc.keyboardHint'); return true;")
    page.open(base + "/tree/cpacs/")
    page.wait_for(TREE_READY, "the tree")
    yield page
    page.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )


def test_the_hint_is_shown_to_a_reader_who_has_not_used_the_keys(unseen):
    hint = unseen.evaluate("""
      var hint = document.getElementById('cd-hint');
      if (!hint) return null;
      return {
        keys: hint.querySelectorAll('kbd').length,
        follows: hint.nextElementSibling ? hint.nextElementSibling.id : null,
        role: hint.getAttribute('role'),
        keyBorder: getComputedStyle(hint.querySelector('kbd')).borderTopWidth
      };
    """)
    assert hint is not None, "a first-time reader should be told"
    # Ahead of the tree in the document, so it is read before what it describes.
    assert hint["follows"] == "cd-tree"
    assert hint["keys"] >= 4
    assert hint["role"] == "note"
    # The keys are the whole point of the strip, so they are set in relief. A
    # rule that stops matching would leave the words and take the keys.
    assert hint["keyBorder"] not in ("0px", "", None), hint["keyBorder"]


def test_the_hint_goes_at_the_first_key_and_does_not_come_back(unseen, base):
    unseen.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    unseen.press("ArrowDown")
    assert unseen.evaluate("return !document.getElementById('cd-hint');")
    unseen.open(base + "/tree/cpacs/")
    unseen.wait_for(TREE_READY, "the tree")
    assert unseen.evaluate("return !document.getElementById('cd-hint');"), "it stays away"


def test_the_hint_can_be_put_away_by_hand(unseen):
    spot = unseen.evaluate("""
      var box = document.querySelector('.cd-hint-close').getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    """)
    unseen.click(spot["x"], spot["y"])
    assert unseen.evaluate("return !document.getElementById('cd-hint');")
