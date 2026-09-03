"""The two panes divide the window, and the page itself does not scroll.

0014 settled that for the tables inside a pane; this is the same rule one level
out. It needs a tree long enough to fill its pane, which is why the module runs
on `crowd.xsd` — 70 elements under the root — rather than on the fixture the
keyboard tests use, where the tree is a dozen rows and no arrangement of the
chrome above it can push the column past the window.

What went wrong: the panes were held to `calc(100vh - 5rem)`, a guess at how
much chrome stands above them. The keyboard hint is 4.6rem more than the guess
allows, and the first key or click of a first visit is what brings the hint out
(0019). The column then ran past the window, the page took a scrollbar, and the
arrows a reader presses in the detail panel scrolled the page instead of the
panel — 70 px at 1500 x 950, and then nothing at all on a type whose panel has
nothing to scroll. Firefox 155 and Chrome behaved alike; only the browser tells
either of them, since none of it is visible in the markup.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "crowd.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

TREE_READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'
LONG_TREE = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 60;'

# What the window holds against what the document wants of it, and whether the
# tree is long enough for the question to mean anything.
FITS = """
  var d = document.documentElement;
  var hint = document.getElementById('cd-hint');
  var tree = document.getElementById('cd-tree');
  return {hint: hint ? Math.round(hint.getBoundingClientRect().height) : 0,
          treeOverflow: tree.scrollHeight - tree.clientHeight,
          overflow: d.scrollHeight - d.clientHeight,
          scrolled: Math.round(window.scrollY),
          focus: document.activeElement.id || document.activeElement.className};
"""


@pytest.fixture
def first_visit(browser, base):
    """The page as a reader who has never used the keys gets it, up to and
    including the click that brings the hint out."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(TREE_READY, "the tree")
    browser.evaluate(
        "window.localStorage.removeItem('cpacs-doc.keyboardHint'); return true;"
    )
    # A path inside `items` opens it, and the tree stands at its 70 rows: the
    # viewer expands the ancestors of the node it is asked for.
    browser.open(base + "/tree/cpacs/items/qq1/")
    browser.wait_for(LONG_TREE, "the open tree")
    spot = browser.evaluate(
        "var box = document.querySelector('.cd-node').getBoundingClientRect();"
        "return {x: box.left + box.width / 2, y: box.top + box.height / 2};"
    )
    browser.click(spot["x"], spot["y"])
    yield browser
    browser.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )


def test_the_tree_is_long_enough_to_fill_its_pane(first_visit):
    """Without this the rest measures nothing: a tree shorter than the window
    leaves room for any amount of chrome above it."""
    fit = first_visit.evaluate(FITS)
    assert fit["treeOverflow"] > 0, fit


def test_the_hint_costs_the_page_no_scrollbar(first_visit):
    fit = first_visit.evaluate(FITS)
    assert fit["hint"] > 0, "the hint is not out, so this measures nothing"
    assert fit["overflow"] == 0, fit


def test_the_arrows_in_the_panel_never_reach_the_page(first_visit):
    """What the reader sees when it does: Enter hands the keyboard to the
    panel, and the arrows the panel is read with slide the whole page instead —
    the strip and the breadcrumb out of the window, and then nothing."""
    first_visit.press("Enter")
    assert first_visit.evaluate(FITS)["focus"] == "cd-detail"
    for _ in range(6):
        first_visit.press("ArrowDown")
    assert first_visit.evaluate(FITS)["scrolled"] == 0
