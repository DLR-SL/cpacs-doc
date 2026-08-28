"""The colour theme, in a browser.

The choice has to hold in two worlds that share no script and no document: the
viewer, and the static pages a citation lands on. What is tested here is mostly
that they agree.
"""

from __future__ import annotations

import pytest

import cdp

SCHEMA = "handbook.xsd"

BROWSER = cdp.find_browser()
pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

# A linked stylesheet arrives after the document. Waiting only for the button
# measures — and clicks — a page that has not been laid out yet, which is what
# CI caught: the attribute was set and the rule that reads it was not in force.
READY = (
    "return document.readyState === 'complete'"
    " && !!document.getElementById('cd-theme');"
)

STATE = """
  var root = document.documentElement;
  var button = document.getElementById('cd-theme');
  return {
    attribute: root.getAttribute('data-theme'),
    scheme: getComputedStyle(root).colorScheme,
    ink: getComputedStyle(document.body).color,
    mode: button ? button.getAttribute('data-mode') : null,
    label: button ? button.getAttribute('aria-label') : null
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the theme button")
    browser.evaluate("window.localStorage.removeItem('cpacs-doc.theme'); return true;")
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the theme button")
    return browser


def state(page) -> dict:
    return page.evaluate(STATE)


def click_theme(page):
    spot = page.evaluate(
        "var box = document.getElementById('cd-theme').getBoundingClientRect();"
        "return { x: box.left + box.width / 2, y: box.top + box.height / 2 };"
    )
    page.click(spot["x"], spot["y"])


def system_is(page, scheme: str):
    page.command("Emulation.setEmulatedMedia", {
        "features": [{"name": "prefers-color-scheme", "value": scheme}]
    })


def test_untouched_it_follows_the_system(page):
    """The absence of a choice is the choice a first visit gets."""
    fresh = state(page)
    assert fresh["attribute"] is None
    assert fresh["scheme"] == "light dark"
    assert fresh["mode"] == "system"

    system_is(page, "dark")
    dark = state(page)["ink"]
    system_is(page, "light")
    light = state(page)["ink"]
    assert dark != light, "the palette should follow the system while nothing is chosen"


def test_the_button_cycles_system_light_dark(page):
    assert state(page)["mode"] == "system"
    click_theme(page)
    chosen = state(page)
    assert chosen["attribute"] == "light" and chosen["scheme"] == "light"
    click_theme(page)
    chosen = state(page)
    assert chosen["attribute"] == "dark" and chosen["scheme"] == "dark"
    # Back to following the system: a first click must not spend a setting
    # that cannot be given back.
    click_theme(page)
    assert state(page)["attribute"] is None
    assert state(page)["scheme"] == "light dark"


def test_the_choice_outranks_the_system(page):
    """Otherwise it is not a choice."""
    system_is(page, "dark")
    click_theme(page)  # light
    chosen = state(page)
    assert chosen["scheme"] == "light"
    system_is(page, "light")
    system_light = state(page)["ink"]
    system_is(page, "dark")
    assert state(page)["ink"] == system_light, "the system should not move a chosen palette"


def test_the_button_says_which_state_it_is_in(page):
    """A control that cycles has to name where it stands and where it goes."""
    assert "system" in state(page)["label"] and "light" in state(page)["label"]
    click_theme(page)
    assert "Colour theme: light" in state(page)["label"]


def test_the_choice_survives_a_reload(page, base):
    click_theme(page)
    click_theme(page)  # dark
    page.open(base + "/tree/cpacs/")
    page.wait_for(READY, "the theme button")
    back = state(page)
    assert back["attribute"] == "dark"
    assert back["mode"] == "dark"


def test_the_choice_carries_over_to_the_pages_a_citation_lands_on(page, base):
    """The viewer and the static pages share neither a script nor a document.
    A reader who picks a palette in one and follows a citable link into the
    other must not be handed the opposite."""
    click_theme(page)
    click_theme(page)  # dark
    for address in ("/doc/1-overview/index.html", "/type/cpacsType/index.html", "/index.html"):
        page.open(base + address)
        page.wait_for(READY, "the theme button on " + address)
        landed = state(page)
        assert landed["attribute"] == "dark", address
        assert landed["scheme"] == "dark", address
        assert landed["mode"] == "dark", address


def test_a_page_can_change_the_theme_for_the_viewer(page, base):
    """It works the other way round too: the control is the same control."""
    page.open(base + "/doc/1-overview/index.html")
    page.wait_for(READY, "the theme button")
    click_theme(page)  # light
    page.open(base + "/tree/cpacs/")
    page.wait_for(READY, "the theme button")
    assert state(page)["attribute"] == "light"


def test_the_palette_is_decided_before_the_stylesheet_arrives(page, base):
    """The point of an inline script is the moment before the stylesheet is in
    force. With the sheet blocked outright, that moment is the whole page: the
    attribute is set and the canvas already knows which way it goes, even
    though not one rule has been read.

    This is the failure CI found, made deliberate. Waiting for the load event
    hides it; blocking the sheet holds it still.
    """
    click_theme(page)
    click_theme(page)  # dark
    page.command("Network.enable")
    page.command("Network.setBlockedURLs", {"urls": ["*styles.css"]})
    try:
        page.open(base + "/doc/1-overview/index.html")
        page.wait_for(READY, "the theme button without a stylesheet")
        stranded = page.evaluate("""
          var root = document.documentElement;
          return {
            attribute: root.getAttribute('data-theme'),
            scheme: getComputedStyle(root).colorScheme,
            inline: root.style.colorScheme,
            styled: getComputedStyle(document.body).maxWidth
          };
        """)
    finally:
        page.command("Network.setBlockedURLs", {"urls": []})
    assert stranded["styled"] == "none", "the stylesheet should not have been applied"
    assert stranded["attribute"] == "dark"
    assert stranded["inline"] == "dark"
    assert stranded["scheme"] == "dark"
