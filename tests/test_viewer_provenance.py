"""Whose words are on the panel, in a browser.

A node's panel carries two kinds of text: what the schema says about this place
and what it says about the type standing there. They were set alike — same
size, same leading — so on the 41,004 nodes of the real schema that carry both
nothing said which was which, and on the 12,980 that carry only the type's, a
general sentence read as a statement about this place.

What belongs to the place stays unmarked; what is borrowed names its owner on a
line of its own, under a bar across the measure. The prose keeps the margin
either way — on many nodes it is the substance of the page — so what is measured
here is the attribution, the rank it is set in, the nesting, and that nothing is
indented.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "provenance.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'

PANEL = r"""
  var panel = document.getElementById('cd-detail');
  var borrowed = panel.querySelector('.cd-borrowed');
  var own = panel.querySelector('.cd-elementdoc');
  var head = borrowed ? borrowed.querySelector('.cd-borrowed-head') : null;
  return {
    meta: panel.querySelector('.cd-kind').textContent.replace(/\s+/g, ' ').trim(),
    own: own ? own.textContent.trim() : null,
    ownIsBorrowed: !!(own && borrowed && borrowed.contains(own)),
    head: head ? head.textContent.replace(/\s+/g, ' ').trim() : null,
    // The two parts read separately. What stands between them on screen is the
    // row's gap, which puts no character into `textContent` — and the route is
    // a button, so nothing runs together in the accessibility tree either.
    label: head && head.querySelector('.cd-borrowed-label')
      ? head.querySelector('.cd-borrowed-label').textContent.replace(/\s+/g, ' ').trim()
      : null,
    headLink: head && head.querySelector('.cd-crumb')
      ? head.querySelector('.cd-crumb').textContent.trim() : null,
    // The label is everything before the route, and none of it may be a
    // control: that is what sent readers out of the panel.
    labelIsPlain: head
      ? !head.querySelector('code button, button code')
        && (!head.querySelector('.cd-crumb')
            || !!head.querySelector('.cd-borrowed-route .cd-crumb'))
      : null,
    labelWeight: head ? getComputedStyle(head).fontWeight : null,
    sizes: head ? [
      parseFloat(getComputedStyle(head).fontSize),
      parseFloat(getComputedStyle(
        head.querySelector('.cd-borrowed-route') || head).fontSize),
      parseFloat(getComputedStyle(borrowed.querySelector('.cd-summary')).fontSize)
    ] : null,
    borrowedText: borrowed ? borrowed.textContent.replace(/\s+/g, ' ').trim() : null,
    tablesInside: borrowed ? borrowed.querySelectorAll('table').length : null,
    // The crossbar, which replaced the tick: it runs the whole measure above
    // the label, so it is the block's own top border and not a mark on the
    // line. Measured as a width, and as how far it reaches.
    mark: borrowed ? getComputedStyle(borrowed).borderTopWidth : null,
    markRuns: borrowed ? Math.round(borrowed.getBoundingClientRect().width) : null,
    // The borrowed prose keeps the margin the place's own words have: it is
    // often the substance of the page, not an aside to the line above it.
    indent: borrowed && own
      ? Math.round(borrowed.querySelector('.cd-summary').getBoundingClientRect().left
                   - own.getBoundingClientRect().left)
      : null
  };
"""


def open_node(browser, base, path):
    browser.open(base + "/tree/cpacs/" + path)
    browser.wait_for(READY, "the tree")
    return browser.evaluate(PANEL)


def test_the_words_of_the_place_stand_outside_the_borrowed_block(browser, base):
    panel = open_node(browser, base, "translation/")
    assert panel["own"] == "Translation of this component, in metres."
    assert not panel["ownIsBorrowed"]
    assert "Point with global reference." in panel["borrowedText"]


def test_the_borrowed_block_says_whose_words_they_are(browser, base):
    panel = open_node(browser, base, "translation/")
    # The line labels the block. "About the type pointType" announced a topic,
    # and readers took it for a heading over a link and clicked through — onto
    # a panel carrying this same prose and these same tables, without the
    # element's own head and words.
    assert panel["label"] == "pointType documentation"
    # Nothing in the label is clickable. The name is what the block is called;
    # the only link says where it leads, and stands after the label.
    assert panel["labelIsPlain"], "the label carries no link"
    assert panel["headLink"] == "show only the type"
    # The mark is a bar across the measure, above the line, not a tick beside
    # it, and it is one stroke as the tick was. It has to reach: what it marks
    # is the join, which a mark at the margin was not saying.
    assert panel["mark"] == "1px"
    assert panel["markRuns"] > 300, f"the bar spans {panel['markRuns']}px"
    # The prose still starts where the place's own words start.
    assert panel["indent"] == 0


def test_the_label_outranks_the_route_that_used_to_outrank_it(browser, base):
    """Measured on the real schema before this: the link held 9.4 to 1 against
    the page where the label held 8.1, underlined and standing first, while the
    label was 31 % smaller than the prose it introduced. So the eye found one
    thing on the line and it was the way out."""
    panel = open_node(browser, base, "translation/")
    label, route, prose = panel["sizes"]
    assert label > route, f"label {label}px, route {route}px"
    # Not a footnote to the block any more. It stays under the prose, since the
    # prose is what the reader came to read.
    assert route < label <= prose, f"label {label}px against prose {prose}px"
    assert panel["labelWeight"] in ("600", "bold")


def test_a_place_that_says_nothing_of_its_own_still_marks_what_it_borrows(browser, base):
    """23.8 % of the nodes in the real schema. The attribution is then the whole
    answer to why the panel reads like a general description."""
    panel = open_node(browser, base, "scaling/")
    assert panel["own"] is None
    assert panel["label"] == "pointType documentation"
    assert "The components are optional" in panel["borrowedText"]


def test_the_tables_are_not_part_of_the_borrowed_block(browser, base):
    """They answer what may stand at this place, and their headings scope them.
    The mark is on the prose, which is the part that could be mistaken for the
    place's own words."""
    panel = open_node(browser, base, "translation/")
    assert panel["tablesInside"] == 0


def test_a_type_with_nothing_to_lend_is_still_named(browser, base):
    """Without a borrowed block the type would be named nowhere on the panel.
    568 of the 54,552 nodes are in that case."""
    panel = open_node(browser, base, "counter/")
    assert panel["head"] is None
    assert "type plainType" in panel["meta"]


def test_the_types_own_panel_marks_nothing(browser, base):
    """Everything there is the type's, so a mark would say nothing."""
    browser.open(base + "/tree/cpacs/translation/")
    browser.wait_for(READY, "the tree")
    browser.evaluate("""
      var head = document.querySelector('#cd-detail .cd-borrowed-head .cd-crumb');
      head.click();
      return true;
    """)
    panel = browser.evaluate(PANEL)
    assert panel["head"] is None
    assert panel["own"] is None
