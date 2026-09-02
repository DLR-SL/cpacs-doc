"""The path above the panel, and getting it out of the browser.

The crumbs are separate buttons with " / " between them, so selecting the line
with the mouse yields `cpacs / header / name` — separators and spaces and all —
and that is the shape that has been going into mails. The button hands over the
path the model holds instead.
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

# The clipboard is the browser's, and reading it back wants a permission this
# driver does not grant. What is asserted is the boundary this code owns: the
# string handed to `writeText`.
STUB = """
  window.__copied = null;
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: function (text) { window.__copied = text; return Promise.resolve(); }
    }
  });
  return true;
"""

LABEL = "return document.querySelector('#cd-detail .cd-copy').textContent;"


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/header/name/")
    browser.wait_for(READY, "the tree")
    return browser


def click(page, selector):
    spot = page.evaluate(
        "var box = document.querySelector('" + selector + "').getBoundingClientRect();"
        "return { x: box.left + box.width / 2, y: box.top + box.height / 2 };"
    )
    page.click(spot["x"], spot["y"])


def test_the_button_copies_the_path_as_an_xpath(page):
    """Absolute, slash separated, no spaces — and no positional predicate: the
    tree is the schema's, so there is no index to state."""
    page.evaluate(STUB)
    click(page, "#cd-detail .cd-copy")
    assert page.evaluate("return window.__copied;") == "/cpacs/header/name"


def test_the_root_on_its_own_is_a_path_too(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    browser.evaluate(STUB)
    click(browser, "#cd-detail .cd-copy")
    assert browser.evaluate("return window.__copied;") == "/cpacs"


def test_the_button_says_what_happened(page):
    """The word is the accessible name, so the outcome is what a reader who
    cannot see the button hears. It goes back to `copy` on its own."""
    assert page.evaluate(LABEL) == "copy"
    page.evaluate(STUB)
    click(page, "#cd-detail .cd-copy")
    assert page.evaluate(LABEL) == "copied"


def test_a_clipboard_that_refuses_is_reported_and_not_papered_over(page):
    """No `navigator.clipboard` outside a secure context, and `execCommand` may
    still say no. Saying "copied" then would be the one unrecoverable answer:
    the reader pastes the previous thing into the mail."""
    page.evaluate("""
      Object.defineProperty(navigator, 'clipboard', {configurable: true, value: undefined});
      document.execCommand = function () { return false; };
      return true;
    """)
    click(page, "#cd-detail .cd-copy")
    assert page.evaluate(LABEL) == "not copied"


def test_the_path_is_on_the_button_for_a_reader_who_hovers(page):
    assert page.evaluate(
        "return document.querySelector('#cd-detail .cd-copy').title;"
    ) == "/cpacs/header/name"
