"""Nested compositors in the diagram's overlay, where a row is a card.

The table indents the name cell and draws its guides in that cell's padding.
In the overlay the cell is one line of a card, and its padding was reset with
every other cell's while the guides stayed: the hairlines ran through the
names of a choice's branches, and every card started at the same edge, so
nothing said which of them a group held. There the card is indented instead.
Measured, as in `test_page_indent.py`, because only the computed layout shows
it.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "nested.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = "return !!document.querySelector('#cd-detail table');"

# Per child: where its card starts, where its name starts, and whether the
# name cell still paints the table's guides. Against the table's left edge.
CARDS = """
  var table = document.querySelector('#cd-detail table');
  var edge = table.getBoundingClientRect().left;
  var cards = {};
  Array.prototype.forEach.call(table.rows, function (row) {
    var name = row.cells[0] && row.cells[0].querySelector('.cd-crumb code');
    if (!name) return;
    var style = getComputedStyle(row);
    cards[name.textContent] = {
      card: Math.round(row.getBoundingClientRect().left + parseFloat(style.paddingLeft) - edge),
      name: Math.round(name.getBoundingClientRect().left - edge),
      guides: getComputedStyle(row.cells[0]).backgroundImage
    };
  });
  return cards;
"""

SLACK = 2


@pytest.fixture(scope="module")
def cards(browser, base):
    browser.open(base + "/diagram/cpacs/holder/")
    browser.wait_for(READY, "the overlay")
    return browser.evaluate(CARDS)


def rem(browser):
    return browser.evaluate(
        "return parseFloat(getComputedStyle(document.documentElement).fontSize);"
    )


def test_a_choice_indents_its_branches_by_one_step(browser, cards):
    step = rem(browser)
    assert abs(cards["always"]["card"]) <= SLACK
    assert abs(cards["either"]["card"] - step) <= SLACK
    assert abs(cards["bothA"]["card"] - 2 * step) <= SLACK
    assert cards["bothA"]["card"] == cards["bothB"]["card"]


def test_names_start_where_their_card_does(cards):
    """The name is the card's first line; no padding of the table's is left
    between them for a guide to stand in."""
    for name, card in cards.items():
        assert abs(card["name"] - card["card"]) <= SLACK, name
        assert card["guides"] == "none", name


def test_a_type_link_stands_at_the_start_of_its_column(browser, cards):
    """A grid item is stretched across its column, and a button centres its
    text: the type stood in the middle of the card."""
    place = browser.evaluate("""
      var cell = document.querySelector('#cd-detail td[data-label="Type"] .cd-crumb').parentNode;
      var link = cell.querySelector('.cd-crumb').getBoundingClientRect();
      var width = cell.getBoundingClientRect().width;
      var label = parseFloat(getComputedStyle(cell, '::before').width);
      return { offset: link.left - cell.getBoundingClientRect().left,
               label: label, width: link.width, cell: width };
    """)
    assert place["width"] < place["cell"] / 2
    # The label column, then the gap: nothing else before the link.
    assert place["offset"] < place["label"] + 0.6 * rem(browser) + SLACK
