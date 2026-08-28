"""What a node says about its type, in a browser.

An element may declare its type on the spot. Until the declaration named that
type, the panel showed no type line and none of what the type holds — in CPACS
3.5.1 that hid 187 of the schema's 265 enumeration values behind a page nothing
linked to.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "handbook.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'

PANEL = r"""
  var panel = document.getElementById('cd-detail');
  var rows = panel.querySelectorAll('table tr');
  var values = [];
  for (var i = 1; i < rows.length; i++) values.push(rows[i].children[0].textContent.trim());
  return {
    text: panel.textContent.replace(/\s+/g, ' '),
    heading: panel.querySelector('h1') ? panel.querySelector('h1').textContent : null,
    tables: panel.querySelectorAll('h2').length,
    values: values
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/mode/")
    browser.wait_for(READY, "the tree")
    return browser


def test_a_node_whose_type_is_declared_inline_shows_it(page):
    panel = page.evaluate(PANEL)
    assert panel["heading"] == "mode"
    # The base is what may be written there; the synthetic name says only where
    # the type was declared, which the breadcrumb has just said.
    assert "Type: xsd:string" in panel["text"]
    assert "cpacsType/mode" not in panel["text"]


def test_the_values_of_that_type_are_reachable_from_the_node(page):
    panel = page.evaluate(PANEL)
    assert "Allowed values" in panel["text"]
    assert panel["values"] == ["inline-only", "second"]


def test_the_type_opens_its_own_page_from_the_panel(page):
    """Anonymous or not, a type keeps a citable address (0003)."""
    page.evaluate("""
      var buttons = document.querySelectorAll('#cd-detail .cd-crumb');
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.indexOf('xsd:string') !== -1) { buttons[i].click(); return true; }
      }
      return false;
    """)
    panel = page.evaluate(PANEL)
    assert panel["heading"] == "cpacsType/mode"
    assert "citable page" in panel["text"]


@pytest.fixture
def constrained(browser, base):
    """A node whose value is narrowed by facets rather than listed."""
    browser.open(base + "/tree/cpacs/ratio/")
    browser.wait_for(READY, "the tree")
    return browser


def test_the_constraints_on_a_value_reach_the_node(constrained):
    """Before they were read at all, a reader could not learn from us that
    `phi` is bounded to 0…360 or that a NACA code is four digits."""
    panel = constrained.evaluate(PANEL)
    assert panel["heading"] == "ratio"
    assert "Type: xsd:double" in panel["text"]
    assert "Value constraints" in panel["text"]
    # The cell holds the word and, clipped inside it, the reading of the word.
    assert [v.split("The value")[0] for v in panel["values"]] == [
        "minInclusive", "maxInclusive",
    ]
    assert "0" in panel["text"] and "1" in panel["text"]


def test_the_schema_word_carries_its_reading(constrained):
    """The word is what the schema says; the reading is what it means. Both,
    the same way a compositor does it."""
    tip = constrained.evaluate("""
      var term = document.querySelector('#cd-detail .cd-facet');
      return term ? { word: term.firstChild.textContent,
                      tip: term.querySelector('.cd-tip').textContent,
                      reachable: term.getAttribute('tabindex') } : null;
    """)
    assert tip is not None
    assert tip["word"] == "minInclusive"
    assert tip["tip"] == "The value must be this or greater."
    assert tip["reachable"] == "0"


def test_the_node_says_what_it_is_worth_unwritten(constrained):
    """`occurs` alone leaves the reader to guess what omitting the element
    means. The schema says it; nothing showed it before."""
    panel = constrained.evaluate(PANEL)
    assert "occurs 0…1 · default 0.5" in panel["text"]


def test_a_column_headed_default_does_not_repeat_the_word(browser, base):
    """The node itself says "default 0.5", because nothing there names the
    field. A table cell sits under a heading that has just named it."""
    # The root node, because that is where a child table with the column is.
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    cell = browser.evaluate("""
      var tables = document.querySelectorAll('#cd-detail table');
      for (var t = 0; t < tables.length; t++) {
        var head = tables[t].querySelector('tr');
        var columns = head.children, at = -1;
        for (var c = 0; c < columns.length; c++) {
          if (columns[c].textContent.trim() === 'Default') at = c;
        }
        if (at === -1) continue;
        var rows = tables[t].querySelectorAll('tr');
        for (var r = 1; r < rows.length; r++) {
          var text = rows[r].children[at] ? rows[r].children[at].textContent.trim() : '';
          if (text) return text;
        }
      }
      return null;
    """)
    assert cell == "0.5", cell


def test_a_node_says_what_may_be_written_into_it(browser, base):
    """`mass` is a `measuredValueType`, which extends `valueBaseType`, which
    extends `xsd:double`. The node named the first and left the reader to walk
    the rest."""
    browser.open(base + "/tree/cpacs/mass/")
    browser.wait_for(READY, "the tree")
    line = browser.evaluate(r"""
      var lines = document.querySelectorAll('#cd-detail .cd-kind');
      for (var i = 0; i < lines.length; i++) {
        var text = lines[i].textContent.replace(/\s+/g, ' ').trim();
        if (text.indexOf('Type:') === 0) return text;
      }
      return null;
    """)
    assert line == "Type: measuredValueType · value xsd:double"


def test_a_row_says_what_sits_behind_the_type_link(browser, base):
    """`xsd:string` in a row looks exactly like the plain string next to it,
    and an inexperienced reader has no reason to click it. The count says there
    is something there, and names the section it leads to."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    rows = browser.evaluate(r"""
      var out = {};
      var rows = document.querySelectorAll('#cd-detail table tr');
      for (var i = 1; i < rows.length; i++) {
        var name = rows[i].children[0];
        var holds = rows[i].querySelector('.cd-holds');
        if (!name) continue;
        out[name.textContent.trim()] = holds ? holds.textContent.trim() : "";
      }
      return out;
    """)
    assert rows.get("mode") == "2 values"
    # Facets are named, not counted: `pattern` says more than "1 constraint",
    # and most rows that carry a facet carry exactly one.
    assert rows.get("ratio") == "minInclusive, maxInclusive"
    # A type that hides nothing leaves the column empty.
    assert rows.get("header") == ""


def test_the_constraints_cell_leads_to_the_values_it_counts(browser, base):
    """Two links in a row lead to one page on purpose. The type name says what
    may be written; these words say that there are two of them, and a reader
    who does not yet know the first follows the second."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    opened = browser.evaluate(r"""
      var cells = document.querySelectorAll('#cd-detail .cd-holds');
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].textContent.trim() === '2 values') { cells[i].click(); return true; }
      }
      return false;
    """)
    assert opened, "no cell counting values was found"
    panel = browser.evaluate(PANEL)
    assert panel["heading"] == "cpacsType/mode"
    assert "Allowed values" in panel["text"]
    assert panel["values"] == ["inline-only", "second"]
