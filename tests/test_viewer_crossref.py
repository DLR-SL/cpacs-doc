"""Cross references in the prose, in a browser.

The static pages resolve them to ordinary links. The viewer cannot: following
one would load a page and throw away the tree and its selection, which is the
whole reason the panel exists. So it links them to the panel instead, and what
these tests check is that both halves of that bargain hold — the click switches
the panel, and the address is still a real one to open elsewhere.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "crossref.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'

LINKS = r"""
  var panel = document.getElementById('cd-detail');
  var links = panel.querySelectorAll('.cd-remarks a');
  var found = [];
  for (var i = 0; i < links.length; i++) {
    found.push({
      text: links[i].textContent,
      href: links[i].getAttribute('href'),
      code: links[i].querySelector('code') ? true : false
    });
  }
  return {
    links: found,
    markers: panel.querySelectorAll('[data-type]').length,
    text: panel.textContent.replace(/\s+/g, ' ')
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/wing/")
    browser.wait_for(READY, "the tree")
    return browser


def test_a_type_name_in_the_prose_links_to_its_type(page):
    """Rule A: the name alone makes the reference, and it stays set as code."""
    state = page.evaluate(LINKS)
    names = [link for link in state["links"] if link["text"] == "wingSectionType"]
    assert len(names) == 1
    assert names[0]["code"] is True
    assert names[0]["href"].endswith("/type/wingSectionType/index.html")


def test_a_hand_written_link_keeps_the_author_s_words(page):
    """Rule C: `ddue:link` names the same type in words of the author's own,
    and those are not schema vocabulary, so they are not set as code."""
    state = page.evaluate(LINKS)
    chosen = [link for link in state["links"] if link["text"] == "a rotor blade"]
    assert len(chosen) == 1
    assert chosen[0]["code"] is False
    assert chosen[0]["href"].endswith("/type/wingSectionType/index.html")


def test_an_element_name_is_not_a_link(page):
    """186 element names in CPACS 3.5.1 are declared with more than one type,
    so a bare element name does not say which page it means."""
    state = page.evaluate(LINKS)
    assert "sections" not in [link["text"] for link in state["links"]]
    assert "sections are its stations" in state["text"]


def test_no_marker_survives_into_the_document(page):
    """The marker is transport between the renderer and this file. Left in
    place it would be picked up again on the next render of the same panel."""
    assert page.evaluate(LINKS)["markers"] == 0


def test_following_a_reference_switches_the_panel_and_keeps_the_tree(page):
    state = page.evaluate(
        """
        var panel = document.getElementById('cd-detail');
        var links = panel.querySelectorAll('.cd-remarks a');
        for (var i = 0; i < links.length; i++) {
          if (links[i].textContent === 'a rotor blade') { links[i].click(); break; }
        }
        return {
          heading: document.querySelector('#cd-detail h1').textContent,
          path: window.location.pathname,
          tree: document.querySelectorAll('[role="treeitem"]').length
        };
        """
    )
    assert state["heading"] == "wingSectionType"
    # The address still names the node the reader came from: the panel showing
    # a cited type is a detour, not a move.
    assert state["path"].endswith("/tree/cpacs/wing/")
    assert state["tree"] > 1
