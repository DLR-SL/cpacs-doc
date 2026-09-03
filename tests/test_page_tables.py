"""A table too wide for the column, in a browser.

The complaint this holds is not that a table scrolls — it has to, being as wide
as its widest name — but that the *page* scrolled with it: heading, prose and
breadcrumb slid out of view while the reader was looking at a column on the
right. That is a matter of computed styles and layout, so it is measured here
rather than asserted on markup (0011).
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "wide.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

PAGE = "/type/longRangeCruisePerformanceSettingsType/index.html"

READY = "return document.readyState === 'complete' && !!document.querySelector('.cd-scroll');"

MEASURE = """
  var host = document.querySelector('.cd-children .cd-scroll');
  var heading = document.querySelector('h1').getBoundingClientRect();
  return {
    page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    table: host.scrollWidth - host.clientWidth,
    column: Math.round(host.clientWidth),
    heading: Math.round(heading.left)
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + PAGE)
    browser.wait_for(READY, "the type page")
    return browser


def test_the_table_is_wider_than_the_column_it_stands_in(page):
    """Without this the rest measures nothing."""
    measured = page.evaluate(MEASURE)
    assert measured["table"] > 0, measured


def test_a_wide_table_does_not_take_the_page_with_it(page):
    assert page.evaluate(MEASURE)["page"] == 0


def test_the_heading_stays_where_it_is_while_the_table_is_read(page):
    before = page.evaluate(MEASURE)
    after = page.evaluate("""
      var host = document.querySelector('.cd-children .cd-scroll');
      host.scrollLeft = host.scrollWidth;
      return {
        scrolled: Math.round(host.scrollLeft),
        page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        heading: Math.round(document.querySelector('h1').getBoundingClientRect().left)
      };
    """)
    assert after["scrolled"] > 0, "the table did not scroll at all"
    assert after["page"] == 0
    assert after["heading"] == before["heading"]


def test_a_tip_on_the_last_row_is_drawn_whole(browser, base):
    """The container clips what leaves it, and the last row's bottom is its
    bottom — so a tip there opens upwards instead of into the clip. 20 of the
    2,319 tips the real schema's tables carry stand in that place."""
    browser.open(base + "/type/cruiseMachNumberType/index.html")
    browser.wait_for(READY, "the constraints page")
    measured = browser.evaluate("""
      var host = document.querySelector('.cd-facets .cd-scroll');
      var rows = host.querySelectorAll('tr');
      var term = rows[rows.length - 1].querySelector('.cd-facet');
      var tip = term.querySelector('.cd-tip');
      var frame = host.getBoundingClientRect();
      var box = tip.getBoundingClientRect();
      return {
        height: Math.round(box.height),
        below: Math.round(box.bottom - frame.bottom),
        above: Math.round(frame.top - box.top),
        overTheTerm: box.bottom <= term.getBoundingClientRect().top + 1
      };
    """)
    assert measured["height"] > 0
    assert measured["overTheTerm"], measured
    assert measured["below"] <= 0 and measured["above"] <= 0, measured


def test_a_tip_stays_inside_the_box_behind_it(page):
    """The term on the *Occurrence* heading stands in a `th`, and `th` is
    `nowrap` so a column head does not break in two. The tip inherited it: it
    held its sentence on one 688 px line inside the 352 px its own `max-width`
    allows, and the words ran out of the white ground and across the page.
    Nothing clips them — the box is what carries the ground."""
    measured = page.evaluate("""
      var term = document.querySelector('.cd-note-term');
      if (!term) return null;
      term.focus();
      var tip = term.querySelector('.cd-tip');
      var style = getComputedStyle(tip);
      var box = tip.getBoundingClientRect();
      var range = document.createRange();
      range.selectNodeContents(tip);
      var text = range.getBoundingClientRect();
      return {
        over: Math.round(text.right - (box.right - parseFloat(style.paddingRight))),
        lines: Math.round(text.height / parseFloat(style.lineHeight))
      };
    """)
    assert measured is not None, "no note term on this page"
    # The premise: a tip short enough to fit on one line would pass the next
    # assertion without the rule that makes it wrap.
    assert measured["lines"] > 1, measured
    assert measured["over"] <= 1, measured
