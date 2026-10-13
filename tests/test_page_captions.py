"""The title of a table and the title of a code block, in a browser.

A table title is rendered as `<caption>`, a code title as `<figcaption>`. The
browser sets the first centred above the table and the second wherever the
stylesheet puts it, so the two titles on one page looked unrelated. Whether
they look alike is a matter of computed styles, so it is measured here.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "captions.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

PAGE = "/type/booleanBaseType/index.html"

READY = "return document.readyState === 'complete' && !!document.querySelector('caption');"

MEASURE = """
  function look(el) {
    var s = getComputedStyle(el);
    return {size: s.fontSize, color: s.color, align: s.textAlign};
  }
  var caption = document.querySelector('caption');
  var table = caption.closest('table').getBoundingClientRect();
  var box = caption.getBoundingClientRect();
  return {
    caption: look(caption),
    figcaption: look(document.querySelector('figcaption')),
    side: getComputedStyle(caption).captionSide,
    left: Math.round(box.left - table.left),
    below: box.top >= caption.closest('table').querySelector('tr:last-child').getBoundingClientRect().bottom - 1
  };
"""


@pytest.fixture
def measured(browser, base):
    browser.open(base + PAGE)
    browser.wait_for(READY, "the type page")
    return browser.evaluate(MEASURE)


def test_a_table_title_looks_like_a_code_title(measured):
    caption, figcaption = measured["caption"], measured["figcaption"]
    assert caption["size"] == figcaption["size"], measured
    assert caption["color"] == figcaption["color"], measured
    assert caption["align"] in ("left", "start"), measured


def test_a_table_title_stands_under_the_table_flush_left(measured):
    assert measured["side"] == "bottom", measured
    assert measured["below"], measured
    assert measured["left"] == 0, measured
