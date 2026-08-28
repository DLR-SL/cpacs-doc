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
