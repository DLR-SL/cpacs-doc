"""What the search shows when one name stands in many places.

53,692 of the entries the real schema produces are elements, and they are 2,224
distinct names: `x` alone stands in 5,448 places and `mass` in 613. A list of
places answers such a query with the same word sixty times over, told apart
only by a path that the column cuts at the front. The fixture here puts one
name in four places and one in two, so the threshold has a case on each side.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "repeat.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'

SEARCH = r"""
  var field = document.getElementById('cd-search');
  var panel = document.getElementById('cd-results');
  return new Promise(function (resolve) {
    var observer = new MutationObserver(function () {
      observer.disconnect();
      var rows = [];
      panel.querySelectorAll('.cd-result').forEach(function (row) {
        rows.push({
          kind: row.getAttribute('data-kind'),
          label: row.querySelector('.cd-result-label').textContent,
          count: row.querySelector('.cd-fold-count')
            ? row.querySelector('.cd-fold-count').textContent : null,
          detail: row.querySelector('.cd-result-detail')
            ? row.querySelector('.cd-result-detail').textContent : null
        });
      });
      resolve({
        rows: rows,
        count: document.getElementById('cd-search-count').textContent
      });
    });
    observer.observe(panel, {childList: true});
    field.value = QUERY;
    field.dispatchEvent(new Event('input', {bubbles: true}));
  });
"""

PLACES = r"""
  var box = document.querySelector('.cd-fold');
  var open = box.querySelector('.cd-result').getAttribute('aria-expanded');
  var list = box.querySelector('.cd-place-list');
  var places = [];
  list.querySelectorAll('.cd-place').forEach(function (row) {
    places.push(row.textContent);
  });
  return {
    expanded: open,
    shown: getComputedStyle(list).display !== 'none',
    mark: box.querySelector('.cd-fold-mark').textContent,
    places: places
  };
"""


def click(page, selector):
    spot = page.evaluate(
        "var box = document.querySelector('" + selector + "').getBoundingClientRect();"
        "return { x: box.left + box.width / 2, y: box.top + box.height / 2 };"
    )
    page.click(spot["x"], spot["y"])


def look_for(page, query):
    """The tab is chosen first: the rows are clicked here, and a pane that is
    not showing has no place on screen to click."""
    click(page, "#cd-tab-search")
    return page.evaluate(SEARCH.replace("QUERY", "'%s'" % query))


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    return browser


def test_a_name_in_many_places_is_one_row_that_says_how_many(page):
    """Four places under one name, and the row carries the count rather than
    four paths that differ in one segment."""
    found = look_for(page, "spot")
    assert [row["label"] for row in found["rows"]] == ["spot", "spotless"]
    assert [row["count"] for row in found["rows"]] == ["4 places", "2 places"]
    # The count is of rows, which is what the list holds: six places, two
    # things to read.
    assert found["count"] == "2"


def test_a_name_folds_from_the_second_place(page):
    """Measured over nine queries on the real schema: every threshold above two
    brings back the truncation grouping is for, because a name in two, three or
    four places is the common case."""
    assert look_for(page, "spotless")["rows"] == [
        {"kind": "element", "label": "spotless", "count": "2 places", "detail": None}
    ]


def test_the_places_open_under_the_name_and_close_again(page):
    """The name is on the row above, so the places carry only where they
    stand."""
    look_for(page, "spot")
    click(page, ".cd-fold .cd-result")
    opened = page.evaluate(PLACES)
    assert opened["expanded"] == "true"
    assert opened["shown"] is True
    assert opened["mark"] == "\u2212"
    assert opened["places"] == ["alpha", "beta", "gamma", "delta"]

    click(page, ".cd-fold .cd-result")
    closed = page.evaluate(PLACES)
    assert closed["expanded"] == "false"
    # Asked of the layout, not of the attribute: `.cd-place-list` sets
    # `display`, which outweighs the browser's own `[hidden]` rule, so the list
    # stayed on screen with `hidden` set and every second click did nothing.
    assert closed["shown"] is False
    assert closed["mark"] == "+"


def test_a_place_goes_to_the_tree_and_leaves_the_query_standing(page):
    """0013: opening a result does not spend the query. What is new is that the
    reader arrives at the place they picked out of a group, not at the name."""
    look_for(page, "spot")
    click(page, ".cd-fold .cd-result")
    click(page, ".cd-place-list .cd-place:nth-child(3)")
    where = page.evaluate("""
      return {
        path: window.location.pathname,
        query: document.getElementById('cd-search').value,
        treeShown: !document.getElementById('cd-tree').hidden
      };
    """)
    assert where["path"].endswith("/tree/cpacs/gamma/spot/")
    assert where["query"] == "spot"
    assert where["treeShown"] is True


def test_what_stands_under_a_name_is_not_an_answer_to_it(page):
    """Every descendant carries the name in its own path, so `alpha` used to be
    answered with `spot` as well. A reader who means a path says so."""
    found = look_for(page, "alpha")
    assert [row["label"] for row in found["rows"]] == ["alpha"]


def test_a_path_query_is_answered_with_places(page):
    """Someone who names a path is asking about places, and folding them back
    into a name would take away the very thing they asked for."""
    found = look_for(page, "alpha/spot")
    assert [row["label"] for row in found["rows"]] == ["spot"]
    assert found["rows"][0]["count"] is None
    assert found["rows"][0]["detail"] == "alpha/spot"
