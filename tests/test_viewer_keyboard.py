"""The viewer's keyboard behaviour, in a browser (F1, N13).

Everything here needs a real browser and nothing else does. The Python tests
see the shell the generator writes; a DOM stand-in sees the logic. Neither sees
a computed style, and a rule that hid the cursor while the arrow keys were
moving it went through both — hence this file.

The browser is shared by the module and each test navigates afresh: starting
one costs about a second, a navigation about a tenth of that.
"""

from __future__ import annotations

import os

import pytest

import cdp

SCHEMA = "minimal.xsd"

BROWSER = cdp.find_browser()
# Skipping quietly is right on a machine without a browser and wrong in CI,
# where it would let this whole file lapse unnoticed.
if BROWSER is None and os.environ.get("CPACS_DOC_REQUIRE_BROWSER"):
    raise RuntimeError(
        "CPACS_DOC_REQUIRE_BROWSER is set and no Chrome or Edge was found"
    )

pytestmark = pytest.mark.skipif(
    BROWSER is None, reason="no Chrome or Edge on this machine"
)

# What the page is asked for after every step. One round trip, so a test reads
# as a sequence of presses rather than as a sequence of queries.
STATE = """
  var rows = Array.prototype.slice.call(document.querySelectorAll('[role="treeitem"]'));
  var cursor = document.querySelector('.cd-node.cd-cursor');
  var active = document.activeElement;
  function label(row) {
    var name = row && row.querySelector('.cd-name');
    return name ? name.textContent : null;
  }
  var style = cursor ? getComputedStyle(cursor) : null;
  return {
    names: rows.map(label),
    cursor: label(cursor),
    outline: style ? style.outlineStyle + " " + style.outlineWidth : null,
    focusIsCursor: active === cursor,
    focus: active ? (active.id || active.className) : null,
    tabStops: rows.filter(function (row) { return row.tabIndex === 0; }).length,
    history: window.history.length,
    scrolled: window.scrollY
  };
"""


TREE_READY = 'return document.querySelectorAll(\'[role="treeitem"]\').length > 1;'


@pytest.fixture(scope="module")
def viewer(browser, base):
    """The hint is shown to a reader who has not used the keys yet. Every test
    but the ones about the hint itself wants the steady state, so it is marked
    as seen once for this origin before anything else runs."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(TREE_READY, "the tree")
    browser.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )
    return browser


@pytest.fixture
def page(viewer, base):
    """A freshly loaded tree, with the keyboard already in it."""
    browser = viewer
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(TREE_READY, "the tree")
    # A reader arrives at the tree by clicking or by Tab; the tests start from
    # there rather than repeating the way in every one of them.
    browser.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    return browser


def state(page) -> dict:
    return page.evaluate(STATE)


def test_the_tree_is_a_single_tab_stop(page):
    """One tab stop for the whole tree, not two per row: the tree has 54,552
    nodes, and tabbing through them is not a way in."""
    assert state(page)["tabStops"] == 1


def test_the_rows_are_owned_by_a_tree(page):
    """The rows are treeitems, so something has to be their tree. The pane
    itself cannot be: with a handbook alongside it is a tab panel."""
    owner = page.evaluate("""
      var row = document.querySelector('[role="treeitem"]');
      var owner = row.closest('[role="tree"]');
      return owner ? { label: owner.getAttribute('aria-label'),
                       inPane: !!owner.closest('#cd-tree') } : null;
    """)
    assert owner is not None, "the treeitems have no tree"
    assert owner["inPane"]
    assert owner["label"] == "Instance tree"


def contrast(a: str, b: str) -> float:
    """WCAG 2.1 contrast between two `rgb()` strings, neither translucent.

    Written out here because the focus ring is the one colour in the viewer
    whose job is a number: it may be as quiet as the design likes down to 3:1
    and not a step below (WCAG 2.4.11), and nothing but the ratio says where
    that step is.
    """
    def channel(colour):
        parts = colour[colour.index("(") + 1:colour.index(")")]
        return [float(v) for v in parts.replace(",", " ").split()[:3]]

    def luminance(colour):
        out = []
        for value in channel(colour):
            value /= 255.0
            out.append(value / 12.92 if value <= 0.04045
                       else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def over(translucent: str, ground: str) -> str:
    """`translucent` composited on an opaque `ground`. The tint a selected row
    lays over the page is given as an rgba(), and a ratio taken against the
    rgba() itself would be a ratio against a colour nobody sees."""
    parts = [float(v) for v in translucent[translucent.index("(") + 1:
                                           translucent.index(")")]
             .replace(",", " ").split()]
    top, alpha = parts[:3], (parts[3] if len(parts) > 3 else 1.0)
    under = [float(v) for v in ground[ground.index("(") + 1:ground.index(")")]
             .replace(",", " ").split()[:3]]
    return "rgb(%f, %f, %f)" % tuple(
        top[i] * alpha + under[i] * (1 - alpha) for i in range(3))


# The row the cursor stands on is the tightest ground the ring meets: it is
# selected, so it carries --field over the page rather than the page itself.
RING = """
  var root = document.documentElement;
  root.setAttribute('data-theme', arguments0);
  root.style.colorScheme = arguments0;
  var cursor = document.querySelector('.cd-node.cd-cursor');
  cursor.focus();
  var ground = null;
  for (var n = cursor; n; n = n.parentElement) {
    var c = getComputedStyle(n).backgroundColor;
    if (c && c !== 'rgba(0, 0, 0, 0)' && c.indexOf('rgba') !== 0) { ground = c; break; }
  }
  var probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;inset:0;background:Canvas;color-scheme:'
    + getComputedStyle(root).colorScheme;
  document.body.appendChild(probe);
  var canvas = getComputedStyle(probe).backgroundColor;
  probe.remove();
  var s = getComputedStyle(cursor);
  return { ring: s.outlineColor, width: s.outlineWidth, page: canvas,
           field: getComputedStyle(root).getPropertyValue('--field').trim() };
"""


def test_the_focus_ring_stays_above_the_line_it_may_not_go_under(page):
    """It was --link and shouted every time the keyboard moved — 6.5 to 1
    against the page. Quiet is the point, and 3:1 is where quiet stops being
    allowed; the margin is what this test keeps."""
    page.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    page.press("ArrowDown")
    page.press(" ")   # selects, so the row carries --field under the ring
    for theme in ("light", "dark"):
        drawn = page.evaluate(RING.replace("arguments0", repr(theme)))
        assert drawn["width"] == "2px", drawn
        # Against the page, and against the tint the selected row lays over it,
        # which is the tighter of the two and so the one that decides.
        assert contrast(drawn["ring"], drawn["page"]) >= 3.0, (theme, drawn)
        row = over(drawn["field"], drawn["page"])
        assert contrast(drawn["ring"], row) >= 3.0, (theme, row, drawn)
    page.evaluate(
        "var r = document.documentElement;"
        "r.removeAttribute('data-theme'); r.style.colorScheme = 'light dark';"
        "return true;"
    )


def test_the_cursor_is_drawn_while_it_holds_the_focus(page):
    """The row the keyboard points at is the row that has the focus, so a rule
    that suppresses the outline on focus takes the cursor with it. That is what
    happened, and nothing but a computed style catches it."""
    before = state(page)
    assert before["focusIsCursor"], f"focus on {before['focus']}"
    assert before["outline"] is not None
    assert "none" not in before["outline"], f"outline: {before['outline']}"


def test_the_arrow_keys_move_the_cursor_and_the_focus_with_it(page):
    start = state(page)
    page.press("ArrowDown")
    moved = state(page)
    assert moved["cursor"] != start["cursor"]
    assert moved["focusIsCursor"], f"focus on {moved['focus']}"
    assert "none" not in moved["outline"]
    page.press("ArrowUp")
    assert state(page)["cursor"] == start["cursor"]


def test_arrow_right_expands_and_the_focus_survives_the_rebuild(page):
    """Expanding replaces the whole tree in the DOM, focused row included."""
    page.press("ArrowDown")          # cpacs -> wings, which has children
    before = state(page)
    page.press("ArrowRight")
    after = state(page)
    assert len(after["names"]) > len(before["names"])
    assert after["cursor"] == before["cursor"]
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_arrow_right_steps_into_the_open_node_and_arrow_left_back_out(page):
    page.press("ArrowDown")
    page.press("ArrowRight")
    parent = state(page)["cursor"]
    page.press("ArrowRight")
    assert state(page)["cursor"] != parent
    page.press("ArrowLeft")
    assert state(page)["cursor"] == parent
    before = len(state(page)["names"])
    page.press("ArrowLeft")
    closed = state(page)
    assert len(closed["names"]) < before, "the parent should be closed"
    assert closed["cursor"] == parent


def test_home_and_end_reach_the_ends_of_what_is_visible(page):
    names = state(page)["names"]
    page.press("End")
    assert state(page)["cursor"] == names[-1]
    page.press("Home")
    assert state(page)["cursor"] == names[0]


def test_arrowing_writes_no_history_entry(page):
    """The cursor is not the selection. Were every arrow key to select, the
    back button would be spent after a few rows."""
    before = state(page)["history"]
    for _ in range(5):
        page.press("ArrowDown")
    assert state(page)["history"] == before


def test_the_arrow_keys_do_not_scroll_the_page_instead(page):
    for _ in range(5):
        page.press("ArrowDown")
    assert state(page)["scrolled"] == 0


def test_space_selects_without_leaving_the_tree(page):
    page.press("ArrowDown")
    before = state(page)["history"]
    page.press(" ")
    after = state(page)
    assert after["history"] == before + 1
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_enter_selects_and_hands_the_keyboard_to_the_detail_panel(page):
    page.press("ArrowDown")
    target = state(page)["cursor"]
    page.press("Enter")
    assert state(page)["focus"] == "cd-detail"
    shown = page.evaluate("return document.getElementById('cd-detail').textContent;")
    assert target in shown
    # The cursor keeps its mark while the keyboard is away, so the way back is
    # visible; Escape is that way back.
    assert state(page)["cursor"] == target
    page.press("Escape")
    assert state(page)["focusIsCursor"]


def test_the_cursor_stands_down_once_the_keyboard_has_left(page):
    """The mark stays, in a different stroke. Both rows carried the same 2px
    solid ring at the same moment, and readers took the ring in the tree to mean
    the keys were still there — then pressed an arrow and scrolled the panel.
    Only a computed style tells the two marks apart."""
    page.press("ArrowDown")
    held = state(page)["outline"]
    assert held == "solid 2px", f"outline while focused: {held}"
    page.press("Enter")
    left = state(page)
    assert left["focus"] == "cd-detail"
    assert left["outline"] == "dashed 1px", f"outline once left: {left['outline']}"
    page.press("Escape")
    assert state(page)["outline"] == "solid 2px"


def test_the_panel_keeps_its_arrows_and_escape_is_the_way_back(page):
    """The panel claims no arrow. It had ArrowLeft, which cost the reader that
    key inside a type page and held only until he tabbed on to a link — while
    Escape had to be learned anyway, and works from either place."""
    page.press("ArrowDown")
    target = state(page)["cursor"]
    page.press("Enter")
    assert state(page)["focus"] == "cd-detail"
    page.press("ArrowLeft")
    held = state(page)
    assert not held["focusIsCursor"], "the panel's own key was taken"
    assert held["focus"] == "cd-detail"
    # Also once the reader has tabbed on: no state of the panel gives the key up.
    moved = page.evaluate(
        "var link = document.querySelector('#cd-detail a, #cd-detail button');"
        "if (!link) return false;"
        "link.focus(); return document.activeElement !== document.getElementById('cd-detail');"
    )
    if moved:
        page.press("ArrowLeft")
        assert not state(page)["focusIsCursor"], "the panel's own key was taken"
    # Escape comes back to the row Enter was pressed on, not to its parent, and
    # the selection behind the panel is untouched.
    page.press("Escape")
    back = state(page)
    assert back["focusIsCursor"], f"focus on {back['focus']}"
    assert back["cursor"] == target


def test_the_keys_work_right_after_a_click(page):
    """A click leaves the focus on the button inside the row, not on the row.
    This is the way most readers reach the tree."""
    spot = page.evaluate("""
      var rows = document.querySelectorAll('[role="treeitem"]');
      var box = rows[rows.length - 1].querySelector('.cd-label').getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2,
               name: rows[rows.length - 1].querySelector('.cd-name').textContent };
    """)
    page.click(spot["x"], spot["y"])
    assert state(page)["cursor"] == spot["name"]
    page.press("ArrowUp")
    after = state(page)
    assert after["cursor"] != spot["name"]
    assert after["focusIsCursor"], f"focus on {after['focus']}"


def test_an_arrow_key_reaches_the_tree_when_the_focus_is_nowhere(page):
    """Straight after a load the focus is nowhere. An arrow key would scroll a
    page that does not scroll — both panes carry their own scrollbar — so it is
    taken into the tree instead, which is what the reader meant."""
    page.evaluate("document.activeElement.blur(); return true;")
    assert page.evaluate("return document.activeElement === document.body;")
    page.press("ArrowDown")
    after = state(page)
    assert after["focusIsCursor"], f"focus on {after['focus']}"
    assert after["scrolled"] == 0


def test_the_tree_is_a_step_or_two_from_the_strip_above_it(page):
    """What matters is that no row of the tree is a tab stop of its own; the
    chrome above it is allowed a control. The field is no longer on that route:
    it lives in the Search tab, and the tree is not on screen beside it."""
    page.evaluate("document.getElementById('cd-tab-tree').focus(); return true;")
    for step in range(1, 4):
        page.press("Tab")
        if state(page)["focusIsCursor"]:
            assert step <= 3, f"the tree took {step} tab stops"
            return
    raise AssertionError("Tab never reached the tree: " + str(state(page)["focus"]))


def test_slash_opens_the_search_and_escape_returns_to_the_cursor(page):
    page.press("ArrowDown")
    cursor = state(page)["cursor"]
    page.press("/")
    assert page.evaluate("return document.activeElement.id;") == "cd-search"
    page.press("Escape")
    after = state(page)
    assert after["focusIsCursor"], f"focus on {after['focus']}"
    assert after["cursor"] == cursor


@pytest.fixture
def unseen(page, base):
    """The page as a first-time reader gets it, up to and including the click
    that brings the hint out. The click is part of the state now: the hint no
    longer stands there from the first paint."""
    page.evaluate("window.localStorage.removeItem('cpacs-doc.keyboardHint'); return true;")
    page.open(base + "/tree/cpacs/")
    page.wait_for(TREE_READY, "the tree")
    click_selector(page, ".cd-node")
    yield page
    page.evaluate(
        "window.localStorage.setItem('cpacs-doc.keyboardHint', 'seen'); return true;"
    )


def test_the_hint_waits_for_the_reader_to_touch_the_tree(page, base):
    """Standing there from the first paint it is furniture. It arrives when the
    reader has just clicked a row and has one question — what now."""
    page.evaluate("window.localStorage.removeItem('cpacs-doc.keyboardHint'); return true;")
    page.open(base + "/tree/cpacs/")
    page.wait_for(TREE_READY, "the tree")
    assert page.evaluate("return !document.getElementById('cd-hint');"), "not at the door"
    click_selector(page, ".cd-node")
    assert page.evaluate("return !!document.getElementById('cd-hint');")


def test_the_hint_stays_away_from_a_reader_already_on_the_keys(page, base):
    """A key before any click says the reader has found them by himself, and
    says it for good: the greeting would be noise on the next page too."""
    page.evaluate("window.localStorage.removeItem('cpacs-doc.keyboardHint'); return true;")
    page.open(base + "/tree/cpacs/")
    page.wait_for(TREE_READY, "the tree")
    page.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    page.press("ArrowDown")
    click_selector(page, ".cd-node")
    assert page.evaluate("return !document.getElementById('cd-hint');")
    page.open(base + "/tree/cpacs/")
    page.wait_for(TREE_READY, "the tree")
    click_selector(page, ".cd-node")
    assert page.evaluate("return !document.getElementById('cd-hint');"), "it stays away"


def test_the_hint_is_shown_to_a_reader_who_has_not_used_the_keys(unseen):
    hint = unseen.evaluate("""
      var hint = document.getElementById('cd-hint');
      if (!hint) return null;
      return {
        keys: hint.querySelectorAll('kbd').length,
        items: hint.querySelectorAll('.cd-hint-item').length,
        follows: hint.nextElementSibling ? hint.nextElementSibling.id : null,
        role: hint.getAttribute('role'),
        keyBorder: getComputedStyle(hint.querySelector('kbd')).borderTopWidth
      };
    """)
    assert hint is not None, "a first-time reader should be told"
    # Ahead of the tree in the document, so it is read before what it describes.
    assert hint["follows"] == "cd-tree"
    # Three caps over three entries: the two that get anyone moving, and the
    # pointer to the `?`, which is a button and so carries no cap. The table
    # the `?` opens has eight over five — that is the one this replaced.
    assert hint["keys"] == 3, hint
    assert hint["items"] == 3, hint
    assert hint["role"] == "note"
    # One row at the tree's default width. Two is a legend, and a legend is
    # what this replaced. Counted as rows the items land on rather than as a
    # height, which moves with the face.
    rows = unseen.evaluate("""
      var line = document.querySelector('#cd-hint .cd-hint-line:not([hidden])');
      var tops = {};
      Array.prototype.forEach.call(line.querySelectorAll('.cd-hint-item'),
        function (n) { tops[Math.round(n.getBoundingClientRect().top)] = 1; });
      return Object.keys(tops).length;
    """)
    assert rows == 1, f"the opening wrapped onto {rows} rows"
    # The keys are the whole point of the strip, so they are set in relief. A
    # rule that stops matching would leave the words and take the keys.
    assert hint["keyBorder"] not in ("0px", "", None), hint["keyBorder"]


def test_the_hint_goes_at_the_first_key_and_does_not_come_back(unseen, base):
    unseen.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    unseen.press("ArrowDown")
    assert unseen.evaluate("return !document.getElementById('cd-hint');")
    unseen.open(base + "/tree/cpacs/")
    unseen.wait_for(TREE_READY, "the tree")
    # The click is what would fetch it, so the click is what has to fail to.
    click_selector(unseen, ".cd-node")
    assert unseen.evaluate("return !document.getElementById('cd-hint');"), "it stays away"


def test_the_hint_can_be_put_away_by_hand(unseen):
    spot = unseen.evaluate("""
      var box = document.querySelector('.cd-hint-close').getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    """)
    unseen.click(spot["x"], spot["y"])
    assert unseen.evaluate("return !document.getElementById('cd-hint');")


def click_help(page):
    spot = page.evaluate("""
      var box = document.getElementById('cd-help').getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    """)
    page.click(spot["x"], spot["y"])


def test_the_question_mark_is_ringed_as_strongly_as_it_is_written(page):
    """Ring and glyph in one ink, or the eye reads the character and not the
    button — and a lone `?` beside a search field looks like a question. The
    ring was --rule-strong against a --ink-soft glyph: 2.6 to 1 where the
    character held 5.9."""
    drawn = page.evaluate("""
      var s = getComputedStyle(document.getElementById('cd-help'));
      return {
        ring: s.borderTopColor,
        ink: s.color,
        radius: s.borderTopLeftRadius,
        width: s.borderTopWidth
      };
    """)
    assert drawn["ring"] == drawn["ink"], drawn
    assert drawn["radius"] == "50%", drawn
    assert drawn["width"] == "1px", drawn


def test_the_help_button_brings_the_hint_back_after_it_was_put_away(page):
    """The keys cannot be read off the tree, so there has to be a way to ask
    for them again — the hint is shown once and then gone for good."""
    assert page.evaluate("return !document.getElementById('cd-hint');")
    click_help(page)
    assert page.evaluate("return !!document.getElementById('cd-hint');")
    assert page.evaluate(
        "return document.getElementById('cd-help').getAttribute('aria-expanded');"
    ) == "true"
    click_help(page)
    assert page.evaluate("return !document.getElementById('cd-hint');"), "it toggles"
    assert page.evaluate(
        "return document.getElementById('cd-help').getAttribute('aria-expanded');"
    ) == "false"


def test_a_hint_the_reader_asked_for_stays_while_the_keys_are_tried(page):
    """The one that appears by itself goes at the first key, having been proved
    superfluous. Snatching away the one that was asked for, because the reader
    tried a key from it, would be the opposite of help."""
    click_help(page)
    page.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    page.press("ArrowDown")
    assert page.evaluate("return !!document.getElementById('cd-hint');")
    page.press("Escape")
    assert page.evaluate("return !document.getElementById('cd-hint');"), "Escape closes it"


def test_the_hint_that_came_by_itself_goes_at_the_first_key(unseen):
    assert unseen.evaluate("return !!document.getElementById('cd-hint');")
    unseen.evaluate("document.querySelector('.cd-node.cd-cursor').focus(); return true;")
    unseen.press("ArrowDown")
    assert unseen.evaluate("return !document.getElementById('cd-hint');")


def click_selector(page, selector):
    spot = page.evaluate(
        "var box = document.querySelector(%r).getBoundingClientRect();"
        "return { x: box.left + box.width / 2, y: box.top + box.height / 2 };" % selector
    )
    page.click(spot["x"], spot["y"])


def test_the_hint_hangs_from_the_strip_rather_than_heading_the_pane(page):
    """It is what the `?` in the strip opens and it outlives the pane below it,
    so it must not read as that pane's heading. Nothing but proximity says
    which it belongs to, so the gap is the assertion: none above, one below."""
    click_help(page)
    gaps = page.evaluate("""
      var strip = document.getElementById('cd-tabs').getBoundingClientRect();
      var hint = document.getElementById('cd-hint').getBoundingClientRect();
      var pane = document.getElementById('cd-tree').getBoundingClientRect();
      return { above: hint.top - strip.bottom, below: pane.top - hint.bottom };
    """)
    assert gaps["above"] < 1, gaps
    assert gaps["below"] >= gaps["above"] + 8, gaps


def shown_groups(page):
    """The leads of the groups a reader can actually see, not the ones in the
    document: a group is put away by `hidden`, and it stays in the DOM."""
    return page.evaluate("""
      return Array.from(document.querySelectorAll('#cd-hint .cd-hint-line'))
        .filter(function (line) { return line.getClientRects().length > 0; })
        .map(function (line) {
          // A group alone in its tab carries no lead: the tab names it.
          var lead = line.querySelector('.cd-hint-lead');
          return lead ? lead.textContent : "";
        });
    """)


def test_the_hint_shows_the_group_for_the_tab_the_reader_is_in(page):
    """It stands over one pane and is read as belonging to it, so it carries
    the keys of that place and no other."""
    click_help(page)
    assert shown_groups(page) == ["", "Legend"]

    click_selector(page, "#cd-tab-search")
    assert shown_groups(page) == ["Start your search with:"]

    click_selector(page, "#cd-tab-tree")
    assert shown_groups(page) == ["", "Legend"]


def test_the_choice_marks_cost_the_tree_no_scrollbars(page):
    """A tip is an absolutely positioned box and belongs to its pane's
    scrollable area whether or not it is on screen. Five of them — this fixture
    is the smallest schema there is — put 272px of scroll into a 219px pane and
    raised both bars over a tree that fits. The words are in the legend now and
    the marks are bare."""
    page.evaluate("""
      for (var pass = 0; pass < 8; pass++) {
        var toggles = document.querySelectorAll('.cd-toggle[aria-expanded="false"]');
        if (!toggles.length) break;
        for (var i = 0; i < toggles.length; i++) toggles[i].click();
      }
      return true;
    """)
    pane = page.evaluate("""
      var p = document.getElementById('cd-tree');
      return {
        marks: document.querySelectorAll('#cd-tree .cd-alternative').length,
        tips: document.querySelectorAll('#cd-tree .cd-tip').length,
        scrollH: p.scrollHeight, clientH: p.clientHeight,
        scrollW: p.scrollWidth, clientW: p.clientWidth
      };
    """)
    assert pane["marks"] > 0, "the fixture has to have choices to mark"
    assert pane["tips"] == 0, pane
    assert pane["scrollH"] == pane["clientH"], pane
    assert pane["scrollW"] == pane["clientW"], pane


def test_the_legend_draws_the_marks_as_the_tree_draws_them(page):
    """What hung off each choice row on hover is a legend now, read once
    instead of hunted for a row at a time. It is drawn from the tree's own
    classes, because a legend that stopped matching the tree would be worse
    than none."""
    click_help(page)
    drawn = page.evaluate("""
      function face(el) {
        if (!el) return null;
        var s = getComputedStyle(el);
        return s.fontWeight + ' ' + s.color + ' ' + s.fontFamily;
      }
      function text(sel) {
        var el = document.querySelector(sel);
        return el ? el.textContent : null;
      }
      return {
        legendRequired: face(document.querySelector('#cd-hint .cd-required .cd-name')),
        treeRequired: face(document.querySelector('#cd-tree .cd-required .cd-name')),
        legendOptional: face(document.querySelector('#cd-hint .cd-optional .cd-name')),
        treeOptional: face(document.querySelector('#cd-tree .cd-optional .cd-name')),
        legendMark: text('#cd-hint .cd-alternative'),
        treeMark: text('#cd-tree .cd-alternative')
      };
    """)
    assert drawn["legendRequired"] == drawn["treeRequired"], drawn
    assert drawn["legendOptional"] == drawn["treeOptional"], drawn
    # And the two say different things, or the legend explains nothing.
    assert drawn["legendRequired"] != drawn["legendOptional"], drawn
    assert drawn["legendMark"] == drawn["treeMark"] != None, drawn


def test_a_heading_stands_over_its_row_and_not_in_it(page):
    """In the item flow, and in a weight 50 off the one the legend uses for
    "must appear", a heading reads as another sample. It sits on a line of its
    own now, flush with what it heads, and it is prose about the schema rather
    than the schema's own words — so the text face against the code face, and
    --ink-soft against --ink."""
    click_help(page)
    seen = page.evaluate("""
      var line = null;
      var lines = document.querySelectorAll('#cd-hint .cd-hint-line');
      for (var i = 0; i < lines.length; i++) {
        if (!lines[i].hidden && lines[i].querySelector('.cd-hint-lead')) line = lines[i];
      }
      if (!line) return null;
      var head = line.querySelector('.cd-hint-lead');
      var item = line.querySelector('.cd-hint-item');
      var sample = line.querySelector('.cd-required .cd-name');
      function face(el) {
        var s = getComputedStyle(el);
        return { family: s.fontFamily.split(',')[0], colour: s.color };
      }
      return {
        text: head.textContent,
        // A whole row to itself: nothing shares its line.
        ownRow: Math.round(head.getBoundingClientRect().bottom)
          <= Math.round(item.getBoundingClientRect().top) + 1,
        headLeft: Math.round(head.getBoundingClientRect().left),
        itemLeft: Math.round(item.getBoundingClientRect().left),
        head: face(head),
        sample: face(sample)
      };
    """)
    assert seen is not None, "the tree tab should carry the legend"
    assert seen["text"] == "Legend", seen
    assert seen["ownRow"], seen
    assert seen["headLeft"] == seen["itemLeft"], seen
    assert seen["head"]["family"] != seen["sample"]["family"], seen
    assert seen["head"]["colour"] != seen["sample"]["colour"], seen


def test_a_rule_divides_the_keys_from_the_legend(page):
    """Two lines in one box saying different kinds of thing. The rule for it
    was already written and was drawing nothing: the Search group stood between
    them in the document, so `.cd-hint-line[hidden] + .cd-hint-line` took the
    rule away — the right rule reading the wrong neighbour."""
    click_help(page)
    edge = page.evaluate("""
      var lines = document.querySelectorAll('#cd-hint .cd-hint-line');
      var shown = [];
      for (var i = 0; i < lines.length; i++) if (!lines[i].hidden) shown.push(lines[i]);
      var s = shown.length > 1 ? getComputedStyle(shown[1]) : null;
      // `--rule` resolved the way the browser resolves it, so the two are
      // compared as colours and not as a hex string against an rgb() one.
      var probe = document.createElement('span');
      probe.style.color = 'var(--rule)';
      document.body.appendChild(probe);
      var quiet = getComputedStyle(probe).color;
      probe.remove();
      return {
        shown: shown.length,
        border: s ? s.borderTopWidth + ' ' + s.borderTopStyle : null,
        colour: s ? s.borderTopColor : null,
        quiet: quiet
      };
    """)
    assert edge["shown"] == 2, edge
    assert edge["border"] == "1px solid", edge
    # The quiet rule of the palette, not ink: it separates, it does not speak.
    assert edge["colour"] == edge["quiet"], edge


def test_the_group_that_is_put_away_takes_its_dividing_rule_with_it(page):
    """The rule divides two groups. Left behind by the group above it, it is a
    line under nothing and a gap at the top of the box."""
    click_help(page)
    click_selector(page, "#cd-tab-search")
    edges = page.evaluate("""
      var hint = document.getElementById('cd-hint').getBoundingClientRect();
      var line = document.querySelector('#cd-hint .cd-hint-line[data-tab="search"]');
      var style = getComputedStyle(line);
      return {
        gap: line.getBoundingClientRect().top - hint.top,
        rule: style.borderTopWidth,
        padding: style.paddingTop
      };
    """)
    assert edges["rule"] in ("0px", "", None), edges
    assert edges["padding"] == "0px", edges
    # Only the box's own padding stands above the group that is showing.
    assert edges["gap"] < 12, edges
