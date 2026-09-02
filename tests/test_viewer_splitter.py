"""How narrow the tree column may be drawn, in a browser.

The column's floor is not a number in the source but the width of the strip at
its top, and only a browser knows that: it is the width of three words and two
round buttons in the reader's own font. Drawn under it, the column does not
clip the strip — it spills the buttons across the splitter and on to the detail
pane, which is what a reader reported as the theme button sitting on the
breadcrumb.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "handbook.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

# The Handbook tab joins the strip only once the model has arrived, and it is
# the widest of the three: measuring before it is there measures a strip that
# is not the one the reader ends up with.
READY = (
    "return document.readyState === 'complete'"
    " && !!document.getElementById('cd-help')"
    " && !document.getElementById('cd-tab-docs').hidden;"
)

LAYOUT = """
  var column = document.querySelector('.cd-column').getBoundingClientRect();
  var detail = document.getElementById('cd-detail').getBoundingClientRect();
  var help = document.getElementById('cd-help').getBoundingClientRect();
  var tabs = document.getElementById('cd-tabs');
  var declared = tabs.style.width;
  tabs.style.width = 'min-content';
  var strip = tabs.scrollWidth;
  tabs.style.width = declared;
  return {column: column.width, strip: strip, help: help.right, detail: detail.left};
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tab strip")
    return browser


def test_the_splitter_stops_at_the_strip(page):
    page.evaluate("document.getElementById('cd-splitter').focus(); return true;")
    for _ in range(30):
        page.press("ArrowLeft")
    layout = page.evaluate(LAYOUT)
    assert layout["column"] >= layout["strip"], "the column was drawn under its own strip"
    assert layout["help"] <= layout["detail"], "the strip reached the detail pane"


def test_a_stored_width_under_the_strip_is_brought_up(page, base):
    """A width stored before the floor existed, or under a narrower strip."""
    page.evaluate("window.localStorage.setItem('cpacs-doc.treeWidth', '200'); return true;")
    page.open(base + "/tree/cpacs/")
    page.wait_for(READY, "the tab strip")
    layout = page.evaluate(LAYOUT)
    assert layout["column"] >= layout["strip"]
    assert layout["help"] <= layout["detail"]
