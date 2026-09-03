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
    label: head && head.querySelector('.cd-borrowed-label')
      ? head.querySelector('.cd-borrowed-label').textContent.replace(/\s+/g, ' ').trim()
      : null,
    // The name is the one control on the line, and the word before it is not.
    headLink: head && head.querySelector('.cd-crumb')
      ? head.querySelector('.cd-crumb').textContent.trim() : null,
    kindIsPlain: head && head.querySelector('.cd-borrowed-kind')
      ? !head.querySelector('.cd-borrowed-kind .cd-crumb') : null,
    labelWeight: head ? getComputedStyle(head).fontWeight : null,
    // Three sizes on one panel: the line, the section headings it stands
    // among, and the prose it introduces.
    sizes: head ? [
      parseFloat(getComputedStyle(head).fontSize),
      parseFloat(getComputedStyle(borrowed.querySelector('.cd-summary')).fontSize)
    ] : null,
    sectionSize: panel.querySelector('h2')
      ? parseFloat(getComputedStyle(panel.querySelector('h2')).fontSize) : null,
    // What the eye finds on the line. The word keeps the soft ink; the name
    // takes the link's, which is the strongest mark this palette has.
    kindInk: head && head.querySelector('.cd-borrowed-kind')
      ? getComputedStyle(head.querySelector('.cd-borrowed-kind')).color : null,
    nameInk: head && head.querySelector('.cd-crumb')
      ? getComputedStyle(head.querySelector('.cd-crumb')).color : null,
    linkInk: getComputedStyle(panel.querySelector('.cd-breadcrumb .cd-crumb')).color,
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
    # element's own head and words. `pointType documentation` then put the
    # unknown word first and the known one last, and an eye running down the
    # panel passed over it; the category word leads now.
    assert panel["label"] == "Type: pointType"
    # The name is the link, and the word before it is not: the reader who wants
    # the type reaches for the name, which is where he would reach anyway.
    assert panel["headLink"] == "pointType"
    assert panel["kindIsPlain"], "the category word is not a control"
    # The mark is a bar across the measure, above the line, not a tick beside
    # it, and it is one stroke as the tick was. It has to reach: what it marks
    # is the join, which a mark at the margin was not saying.
    assert panel["mark"] == "1px"
    assert panel["markRuns"] > 300, f"the bar spans {panel['markRuns']}px"
    # The prose still starts where the place's own words start.
    assert panel["indent"] == 0


def test_the_name_is_what_the_eye_finds_on_the_line(browser, base):
    """The line was passed over when it read `<name> documentation` at
    --step-0, and again when the name was plain text at --step-2 with the route
    beside it. What was missing was a mark the eye recognises, not size: the
    name carries the link's hue and its underline, and nothing else on the line
    does."""
    panel = open_node(browser, base, "translation/")
    assert panel["nameInk"] == panel["linkInk"], panel["nameInk"]
    assert panel["kindInk"] != panel["nameInk"], panel["kindInk"]


def test_the_line_ranks_under_the_headings_and_under_the_prose(browser, base):
    """A step under `Attributes` and `Child elements`, so the block does not
    outrank the sections around it, and under the prose, which is what the
    reader came to read. It was raised to their size for one revision, while
    the name was still plain text; with the link on the name that step made it
    the loudest thing on the panel."""
    panel = open_node(browser, base, "translation/")
    label, prose = panel["sizes"]
    assert label < panel["sectionSize"], f"label {label}px, headings {panel['sectionSize']}px"
    assert label < prose, f"label {label}px against prose {prose}px"
    # The weight is what still makes it a heading rather than a caption: at
    # --step-0 and 400 it was 31 % smaller than the prose it introduces.
    assert panel["labelWeight"] in ("600", "bold")


def test_a_place_that_says_nothing_of_its_own_still_marks_what_it_borrows(browser, base):
    """23.8 % of the nodes in the real schema. The attribution is then the whole
    answer to why the panel reads like a general description."""
    panel = open_node(browser, base, "scaling/")
    assert panel["own"] is None
    assert panel["label"] == "Type: pointType"
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
