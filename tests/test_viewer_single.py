"""The one-file documentation, opened from a disk (`build --single`).

This is the form that has no server behind it, and every property that makes it
work is a property the deployed form does not need: the model comes out of the
document because `fetch` on a file:// URL is refused, the address lives in the
fragment because `pushState` to a path throws a SecurityError against a null
origin, and the links to citable pages are gone because those pages are not
written. None of that can be judged anywhere but in a browser on a real file.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import cdp

from cpacs_doc import generator, serve as serve_module

FIXTURES = Path(__file__).parent / "fixtures"

SCHEMA = "handbook.xsd"

BROWSER = cdp.find_browser()
if BROWSER is None and os.environ.get("CPACS_DOC_REQUIRE_BROWSER"):
    raise RuntimeError(
        "CPACS_DOC_REQUIRE_BROWSER is set and no Chrome or Edge was found"
    )

pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'

HEADING = "(document.querySelector('#cd-detail h1') || {}).textContent"


@pytest.fixture(scope="module")
def single(tmp_path_factory):
    """The fixture schema as one file, addressed the way a reader opens it."""
    directory = tmp_path_factory.mktemp("single")
    schema = directory / SCHEMA
    shutil.copyfile(FIXTURES / SCHEMA, schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=directory / "media", limit=0
    )
    assert site.rebuild()
    generator.generate_single(site.model, directory)
    return (directory / generator.SINGLE_NAME).as_uri()


def test_the_model_is_read_out_of_the_document(browser, single):
    """Nothing is fetched: on file:// the request would be refused, and the
    empty viewer that follows was the whole reason for this form."""
    browser.open(single)
    browser.wait_for(READY, "the tree")
    assert browser.evaluate(f"return {HEADING};") == "cpacs"
    assert browser.evaluate("return document.getElementById('cd-model') !== null;")


def test_a_selection_writes_the_address_into_the_fragment(browser, single):
    browser.open(single)
    browser.wait_for(READY, "the tree")
    # The first press puts the cursor on the root, the second on its first
    # child: the cursor is not the selection (0010).
    browser.press("ArrowDown")
    browser.press("ArrowDown")
    browser.press("Enter")
    browser.wait_for("return window.location.hash.length > 1;", "the address")
    assert browser.evaluate("return window.location.hash;").startswith("#/tree/cpacs/")


def test_an_address_typed_into_the_fragment_opens_that_node(browser, single):
    browser.open(single)
    browser.wait_for(READY, "the tree")
    browser.evaluate('window.location.hash = "/tree/cpacs/header/"; return true;')
    browser.wait_for(f"return {HEADING} === 'header';", "the node")


def test_the_fragment_is_read_when_the_file_is_opened_at_one(browser, single):
    """The address is handed over as a whole — a link into the documentation is
    a link to the file plus a fragment, and it must open there rather than at
    the root (0022)."""
    browser.open(single + "#/tree/cpacs/header/")
    browser.wait_for(READY, "the tree")
    assert browser.evaluate(f"return {HEADING};") == "header"


def test_back_returns_to_the_node_before(browser, single):
    browser.open(single)
    browser.wait_for(READY, "the tree")
    # The first press puts the cursor on the root, the second on its first
    # child: the cursor is not the selection (0010).
    browser.press("ArrowDown")
    browser.press("ArrowDown")
    browser.press("Enter")
    browser.wait_for("return window.location.hash.length > 1;", "the address")
    assert browser.evaluate(f"return {HEADING};") != "cpacs"
    browser.evaluate("window.history.back(); return true;")
    browser.wait_for(f"return {HEADING} === 'cpacs';", "the root")


def test_a_type_still_opens_in_the_panel_but_offers_no_page_to_cite(browser, single):
    """The panel switch is what shows a type here (0026); the citable page it
    otherwise offers is not written in this form, so it is not linked."""
    browser.open(single + "#/tree/cpacs/header/")
    browser.wait_for(READY, "the tree")
    opened = browser.evaluate("""
      var buttons = document.querySelectorAll('#cd-detail button'), target = null;
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].querySelector('code')) { target = buttons[i]; break; }
      }
      if (!target) return null;
      target.click();
      return document.querySelector('#cd-detail h1').textContent;
    """)
    assert opened == "headerType"
    assert browser.evaluate("""
      var links = document.querySelectorAll('#cd-detail a[href]'), out = [];
      for (var i = 0; i < links.length; i++) {
        var href = links[i].getAttribute('href');
        // The reference for a built-in type is the one link that leads
        // somewhere real from here.
        if (href.indexOf('http') !== 0) out.push(href);
      }
      return out;
    """) == []
