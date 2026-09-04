"""What the search shows, in a browser.

Of the 58,920 entries the real schema produces, 53,692 are elements. A single
ranked list therefore answered a broad query with elements alone: `segment`
matched 21,496 entries, all sixty shown were elements, and the 61 matching types
were not mentioned. The fixture here reproduces that in miniature.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "crowd.xsd"

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
      var kinds = {};
      panel.querySelectorAll('.cd-result').forEach(function (row) {
        var kind = row.getAttribute('data-kind');
        kinds[kind] = (kinds[kind] || 0) + 1;
      });
      var chips = [];
      panel.querySelectorAll('.cd-filter').forEach(function (chip) {
        chips.push({
          text: chip.textContent.trim(),
          pressed: chip.getAttribute('aria-pressed') === 'true',
          disabled: chip.disabled
        });
      });
      resolve({
        kinds: kinds,
        chips: chips,
        count: document.getElementById('cd-search-count').textContent
      });
    });
    observer.observe(panel, {childList: true});
    field.value = QUERY;
    field.dispatchEvent(new Event('input', {bubbles: true}));
  });
"""


def look_for(browser, query):
    return browser.evaluate(SEARCH.replace("QUERY", "'%s'" % query))


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    # A fresh load, so the filter chosen by another test is gone with it.
    return browser


def test_a_type_is_not_crowded_out_by_the_elements(page):
    """70 elements and one type match; the elements alone would fill all sixty
    places, and the type would be the one left out."""
    found = look_for(page, "qq")
    assert found["kinds"].get("type") == 1
    assert found["kinds"].get("attribute") == 1
    assert found["kinds"].get("element") == 58
    assert found["count"] == "60 of 72"


def test_the_chips_count_every_match_not_only_the_shown(page):
    """The count is what tells the reader that a kind exists at all — 60 of 71
    says nothing about which kinds the 11 unshown ones are."""
    chips = look_for(page, "qq")["chips"]
    assert [chip["text"] for chip in chips] == [
        "All 72", "Elements 70", "Types 1", "Attributes 1"
    ]
    assert chips[0]["pressed"] is True
    # A kind with nothing to show cannot be chosen, and says why by its count.
    assert look_for(page, "qq1")["chips"][2]["disabled"] is True


def test_narrowing_to_one_kind_holds_across_the_next_query(page):
    """Someone who searches types searches types again. A filter that reset on
    every keystroke would cost the click it was meant to save."""
    look_for(page, "qq")
    page.evaluate("""
      var chips = document.querySelectorAll('.cd-filter');
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].textContent.indexOf('Types') === 0) { chips[i].click(); return true; }
      }
      return false;
    """)
    narrowed = page.evaluate("""
      var panel = document.getElementById('cd-results');
      var kinds = {};
      panel.querySelectorAll('.cd-result').forEach(function (row) {
        var kind = row.getAttribute('data-kind');
        kinds[kind] = (kinds[kind] || 0) + 1;
      });
      return {kinds: kinds, count: document.getElementById('cd-search-count').textContent};
    """)
    assert narrowed["kinds"] == {"type": 1}
    assert narrowed["count"] == "1"
    # The reader who narrowed by hand is told the shortcut for next time.
    assert "same as typing" in page.evaluate(
        "return document.querySelector('.cd-filter-note').textContent;"
    )

    again = look_for(page, "qqType")
    assert again["kinds"] == {"type": 1}
    assert [chip["pressed"] for chip in again["chips"]] == [False, False, True, False]


def test_a_prefix_narrows_without_the_mouse(page):
    """The chips and the prefixes are one switch with two spellings. Whoever
    knows what they are after should not have to reach for the pointer."""
    found = look_for(page, "type:qq")
    assert found["kinds"] == {"type": 1}
    assert [chip["pressed"] for chip in found["chips"]] == [False, False, True, False]
    # And it says so without the note: the reader is already taking the shortcut.
    assert page.evaluate("return !document.querySelector('.cd-filter-note');") is True

    assert look_for(page, "@qq")["kinds"] == {"attribute": 1}
    assert look_for(page, "element:qq")["kinds"].get("type") is None


def test_a_prefix_alone_asks_for_the_whole_kind(page):
    """`type:` is a fair question — every type there is — and the two-character
    minimum would otherwise refuse to answer it."""
    assert look_for(page, "type:")["kinds"] == {"type": 3}  # qqType, crowdType, rootType


def test_a_query_with_a_slash_is_a_path_and_nothing_else(page):
    """Someone typing `items/qq1` is not looking for the word in a description,
    and the shortest path is the one they meant."""
    found = look_for(page, "items/qq1")
    assert "type" not in found["kinds"]
    first = page.evaluate(
        "return document.querySelector('.cd-result .cd-result-label').textContent;"
    )
    assert first == "qq1"


def test_choosing_a_chip_takes_the_prefix_out_of_the_field(page):
    """A field reading `type:` under a pressed All would be a lie: one switch,
    so whichever spelling the reader used last is the one that stands."""
    look_for(page, "type:qq")
    page.evaluate("""
      var chips = document.querySelectorAll('.cd-filter');
      for (var i = 0; i < chips.length; i++) {
        if (chips[i].textContent.indexOf('All') === 0) { chips[i].click(); return true; }
      }
      return false;
    """)
    assert page.evaluate("return document.getElementById('cd-search').value;") == "qq"


# Where the ring the keyboard leaves behind is painted, against the box the
# panel may paint in. `clientWidth`/`clientHeight` rather than the rect, so a
# scrollbar the panel has taken does not count as room.
RING = r"""
  var row = document.activeElement;
  var panel = document.getElementById('cd-results');
  var style = window.getComputedStyle(row);
  var reach = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
  var r = row.getBoundingClientRect();
  var p = panel.getBoundingClientRect();
  return {
    row: row.className,
    ring: style.outlineStyle,
    top: Math.round((r.top - reach) - p.top),
    bottom: Math.round((p.top + panel.clientHeight) - (r.bottom + reach)),
    left: Math.round((r.left - reach) - p.left),
    right: Math.round((p.left + panel.clientWidth) - (r.right + reach))
  };
"""


def test_the_ring_on_a_result_is_not_cut_off_by_the_pane(page):
    """The rows fill the width of a pane that scrolls, and the arrow that moves
    the focus parks the row flush against the pane's edge. A ring drawn outside
    the row is then cut off — on both sides always, and along the edge the row
    was brought to as soon as the reader is past the first screenful. So it is
    drawn inside the row instead, as it is on the tree's nodes.
    """
    page.evaluate("document.getElementById('cd-tab-search').click(); return true;")
    look_for(page, "qq")
    page.evaluate("document.getElementById('cd-search').focus(); return true;")
    # Into the list, and then far enough down that the pane has had to scroll.
    for _ in range(30):
        page.press("ArrowDown")
    bottom = page.evaluate(RING)
    assert "cd-result" in bottom["row"], "the arrows did not reach the results"
    assert bottom["ring"] == "solid", "the focused row carries no ring"
    for side in ("top", "bottom", "left", "right"):
        assert bottom[side] >= 0, "the ring is cut off at the %s: %r" % (side, bottom)

    # And on the way back, where the row is brought to the other edge.
    for _ in range(25):
        page.press("ArrowUp")
    top = page.evaluate(RING)
    for side in ("top", "bottom", "left", "right"):
        assert top[side] >= 0, "the ring is cut off at the %s: %r" % (side, top)
