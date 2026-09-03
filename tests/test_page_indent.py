"""How far in a child row starts, measured rather than asserted on markup.

The depth is written into the markup as a custom property and turned into a
padding by one stylesheet rule, so markup alone says nothing about where a row
actually begins. It said nothing about the defect either: every compositor row
sat at 0.45rem whatever its depth, because `.cd-group td:first-child` outweighs
`td.cd-indent` on specificity. A `choice` stood to the left of the elements it
is a sibling of, and the sequences inside it began where the outermost one
does — the one thing the column exists to show, gone. Computed styles are the
only place that is visible (0011).
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "content.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

# sequence > [always, choice > [either, sequence > [bothA, bothB]]]: a
# compositor at every level the rule has to serve.
PAGE = "/type/choiceType/index.html"
READY = "return document.readyState === 'complete' && !!document.querySelector('.cd-children table');"

# Where each row's mark or name begins, against the table's own left edge, by
# what the row is called. A group is read by its mark rather than its word: the
# word is what the reader compares across levels, but the mark is what stands
# at the front of the row. Rounded, because the columns are laid out in
# fractional pixels and the question is which level a row sits at.
STARTS = """
  var table = document.querySelector('.cd-children table');
  var edge = table.getBoundingClientRect().left;
  var starts = {};
  Array.prototype.forEach.call(table.rows, function (row) {
    var cell = row.cells[0];
    var term = cell.querySelector('.cd-group-term');
    var inner = term ? cell.querySelector('.cd-group-mark') : cell.querySelector('code');
    if (!inner) return;
    var key = (term || inner).firstChild.nodeValue.trim();
    var seen = starts[key] || (starts[key] = []);
    seen.push(Math.round(inner.getBoundingClientRect().left - edge));
  });
  return starts;
"""

# One fractional pixel, lost to rounding twice over.
SLACK = 2


@pytest.fixture
def starts(browser, base):
    browser.open(base + PAGE)
    browser.wait_for(READY, "the type page")
    return browser.evaluate(STARTS)


def test_a_group_stands_where_its_siblings_do(starts):
    """The `choice` is a sibling of `always`, so its mark begins where that
    name begins. It began a level and a half to the left of it."""
    assert starts["choice"] == [starts["always"][0]], starts


def test_a_nested_group_stands_one_level_in(starts):
    """The sequence inside the choice heads rows of its own, so it sits a
    level below it — where `either`, its sibling, sits. The outermost sequence
    heads the table and stands in its own well, left of everything."""
    assert starts["sequence"][1:] == [starts["either"][0]], starts
    assert starts["sequence"][0] < starts["always"][0], starts


def test_every_level_is_one_step_further_in(starts):
    """One rule, one step: the ladder has to be even or it reads as noise."""
    step = starts["either"][0] - starts["always"][0]
    assert step > 0, starts
    assert abs(starts["bothA"][0] - starts["either"][0] - step) <= SLACK, starts
    assert starts["bothB"] == starts["bothA"], starts
