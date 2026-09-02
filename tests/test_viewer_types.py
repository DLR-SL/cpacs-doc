"""What a node says about its type, in a browser.

An element may declare its type on the spot. Until the declaration named that
type, the panel showed no type line and none of what the type holds — in CPACS
3.5.1 that hid 187 of the schema's 265 enumeration values behind a page nothing
linked to.
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

PANEL = r"""
  var panel = document.getElementById('cd-detail');
  var first = panel.querySelector('table');
  var rows = first ? first.querySelectorAll('tr') : [];
  var values = [];
  for (var i = 1; i < rows.length; i++) values.push(rows[i].children[0].textContent.trim());
  return {
    text: panel.textContent.replace(/\s+/g, ' '),
    heading: panel.querySelector('h1') ? panel.querySelector('h1').textContent : null,
    tables: panel.querySelectorAll('h2').length,
    values: values
  };
"""


@pytest.fixture
def page(browser, base):
    browser.open(base + "/tree/cpacs/mode/")
    browser.wait_for(READY, "the tree")
    return browser


def test_a_node_whose_type_is_declared_inline_shows_it(page):
    panel = page.evaluate(PANEL)
    assert panel["heading"] == "mode"
    # The base is what may be written there; the synthetic name says only where
    # the type was declared, which the breadcrumb has just said.
    assert "Value: text (xsd:string)" in panel["text"]
    assert "cpacsType/mode" not in panel["text"]


def test_a_declaration_naming_a_builtin_outright_says_it_as_the_value(browser, base):
    """`type="xsd:string"` on the declaration: there is no type in the schema to
    have a page, so the type is the value and the head has no business naming it
    twice. `cpacs/header/version` is one of the five in the real schema, and it
    is among the first nodes anyone opens."""
    browser.open(base + "/tree/cpacs/header/name/")
    browser.wait_for(READY, "the tree")
    lines = browser.evaluate(r"""
      var out = [];
      document.querySelectorAll('#cd-detail .cd-head .cd-kind').forEach(function (line) {
        out.push(line.textContent.replace(/\s+/g, ' ').trim());
      });
      return out;
    """)
    assert lines[1] == "Value: text (xsd:string)", lines
    assert "type xsd:string" not in lines[0], lines


def test_the_values_of_that_type_are_reachable_from_the_node(page):
    panel = page.evaluate(PANEL)
    assert "Allowed values" in panel["text"]
    assert panel["values"] == ["inline-only", "second"]


def test_the_type_opens_its_own_page_from_the_panel(page):
    """Anonymous or not, a type keeps a citable address (0003)."""
    page.evaluate("""
      var buttons = document.querySelectorAll('#cd-detail .cd-crumb');
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.indexOf('xsd:string') !== -1) { buttons[i].click(); return true; }
      }
      return false;
    """)
    panel = page.evaluate(PANEL)
    assert panel["heading"] == "cpacsType/mode"
    assert "citable page" in panel["text"]


@pytest.fixture
def constrained(browser, base):
    """A node whose value is narrowed by facets rather than listed."""
    browser.open(base + "/tree/cpacs/ratio/")
    browser.wait_for(READY, "the tree")
    return browser


def test_the_constraints_on_a_value_reach_the_node(constrained):
    """Before they were read at all, a reader could not learn from us that
    `phi` is bounded to 0…360 or that a NACA code is four digits."""
    panel = constrained.evaluate(PANEL)
    assert panel["heading"] == "ratio"
    assert "Value: decimal number (xsd:double)" in panel["text"]
    assert "Value constraints" in panel["text"]
    # The cell holds the word and, clipped inside it, the reading of the word.
    assert [v.split("The value")[0] for v in panel["values"]] == [
        "minInclusive", "maxInclusive",
    ]
    assert "0" in panel["text"] and "1" in panel["text"]


def test_the_value_line_says_what_narrows_it(constrained):
    """1,199 of the real schema's 54,552 nodes have something behind the value —
    a pattern, a range, a list of values. The table that spells it out sits
    further down the same panel; the head says that there is one."""
    lines = constrained.evaluate(r"""
      var out = [];
      document.querySelectorAll('#cd-detail .cd-kind').forEach(function (line) {
        out.push(line.textContent.replace(/\s+/g, ' ').trim());
      });
      return out;
    """)
    # Named rather than counted, as the Constraints column names them.
    assert lines[1] == "Value: decimal number (xsd:double) · minInclusive, maxInclusive", lines


def test_the_schema_word_carries_its_reading(constrained):
    """The word is what the schema says; the reading is what it means. Both,
    the same way a compositor does it."""
    tip = constrained.evaluate("""
      var term = document.querySelector('#cd-detail .cd-facet');
      return term ? { word: term.firstChild.textContent,
                      tip: term.querySelector('.cd-tip').textContent,
                      reachable: term.getAttribute('tabindex') } : null;
    """)
    assert tip is not None
    assert tip["word"] == "minInclusive"
    assert tip["tip"] == "The value must be this or greater."
    assert tip["reachable"] == "0"


def test_the_node_says_what_it_is_worth_unwritten(constrained):
    """`occurs` alone leaves the reader to guess what omitting the element
    means. The schema says it; nothing showed it before."""
    panel = constrained.evaluate(PANEL)
    assert "Occurrence: may appear at most once [0..1] · default 0.5" in panel["text"]


def test_the_node_line_says_whether_it_is_a_rule(browser, base):
    """`occurs 1` read as a count of what is in a dataset. The modal is the
    part that says the schema is demanding it, and the node line is read
    rather than scanned, so it can afford the sentence."""
    browser.open(base + "/tree/cpacs/header/")
    browser.wait_for(READY, "the tree")
    assert "Occurrence: must appear exactly once [1..1]" in browser.evaluate(PANEL)["text"]


def test_a_column_headed_default_does_not_repeat_the_word(browser, base):
    """The node itself says "default 0.5", because nothing there names the
    field. A table cell sits under a heading that has just named it."""
    # The root node, because that is where a child table with the column is.
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    cell = browser.evaluate("""
      var tables = document.querySelectorAll('#cd-detail table');
      for (var t = 0; t < tables.length; t++) {
        var head = tables[t].querySelector('tr');
        var columns = head.children, at = -1;
        for (var c = 0; c < columns.length; c++) {
          if (columns[c].textContent.trim() === 'Default') at = c;
        }
        if (at === -1) continue;
        var rows = tables[t].querySelectorAll('tr');
        for (var r = 1; r < rows.length; r++) {
          var text = rows[r].children[at] ? rows[r].children[at].textContent.trim() : '';
          if (text) return text;
        }
      }
      return null;
    """)
    assert cell == "0.5", cell


def test_a_node_says_what_may_be_written_into_it(browser, base):
    """`mass` is a `measuredValueType`, which extends `valueBaseType`, which
    extends `xsd:double`. The node named the first and left the reader to walk
    the rest."""
    browser.open(base + "/tree/cpacs/mass/")
    browser.wait_for(READY, "the tree")
    lines = browser.evaluate(r"""
      var out = [];
      document.querySelectorAll('#cd-detail .cd-kind').forEach(function (line) {
        out.push(line.textContent.replace(/\s+/g, ' ').trim());
      });
      return out;
    """)
    # The type stands on the first line because `measuredValueType` has no words
    # of its own to lend; where a type has them, its name heads those instead.
    # What may be written here is a second question and has a line of its own.
    assert lines[0].endswith("· type measuredValueType"), lines
    # The plain word leads, the schema's own name follows in brackets and
    # carries the link.
    assert lines[1] == "Value: decimal number (xsd:double)", lines


def test_the_value_leads_to_what_that_datatype_allows(browser, base):
    """Nothing here says what `xsd:double` permits, and looking it up meant
    leaving the documentation. The reference answers it; the link opens beside
    the viewer rather than in place of it."""
    browser.open(base + "/tree/cpacs/mass/")
    browser.wait_for(READY, "the tree")
    link = browser.evaluate("""
      var link = document.querySelector('#cd-detail .cd-builtin');
      return link ? { href: link.href, target: link.target,
                      rel: link.rel, text: link.textContent.trim() } : null;
    """)
    assert link is not None
    assert link["text"] == "xsd:double"
    assert link["href"].endswith("/t-xsd_double.html")
    assert link["target"] == "_blank"
    assert "noopener" in link["rel"]


def test_a_name_that_leads_off_the_site_is_set_quieter_than_one_that_does_not(browser, base):
    """A type name leads further into what is written here; a built-in name is
    the last stop and leaves. `xsd:string` stands in 3,624 rows of the real
    schema, so the difference is carried by ink rather than by a mark on every
    one of them — and by the underline, which is what says "link" at all."""
    browser.open(base + "/tree/cpacs/mass/")
    browser.wait_for(READY, "the tree")
    ink = browser.evaluate("""
      var out = {};
      var builtin = document.querySelector('#cd-detail .cd-builtin');
      var inside = document.querySelector('#cd-detail .cd-kind .cd-crumb');
      out.builtin = getComputedStyle(builtin).color;
      out.builtinUnderline = getComputedStyle(builtin).textDecorationLine;
      out.inside = inside ? getComputedStyle(inside).color : null;
      // Resolved rather than read as a string: what the assertion is about is
      // that the name takes the palette's soft ink, whatever that is set to,
      // and a hex literal in a test turns every tuning of the palette into a
      // failure that says nothing.
      var probe = document.createElement("span");
      probe.style.color = "var(--ink-soft)";
      document.body.appendChild(probe);
      out.soft = getComputedStyle(probe).color;
      probe.remove();
      return out;
    """)
    assert ink["builtin"] != ink["inside"]
    assert ink["builtinUnderline"] == "underline"
    # The soft ink, not a colour of its own: one palette, two roles.
    assert ink["builtin"] == ink["soft"]


def test_a_row_says_what_sits_behind_the_type_link(browser, base):
    """`xsd:string` in a row looks exactly like the plain string next to it,
    and an inexperienced reader has no reason to click it. The count says there
    is something there, and names the section it leads to."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    rows = browser.evaluate(r"""
      var out = {};
      var rows = document.querySelectorAll('#cd-detail table tr');
      for (var i = 1; i < rows.length; i++) {
        var name = rows[i].children[0];
        var holds = rows[i].querySelector('.cd-holds');
        if (!name) continue;
        out[name.textContent.trim()] = holds ? holds.textContent.trim() : "";
      }
      return out;
    """)
    assert rows.get("mode") == "2 values"
    # Facets are named, not counted: `pattern` says more than "1 constraint",
    # and most rows that carry a facet carry exactly one.
    assert rows.get("ratio") == "minInclusive, maxInclusive"
    # A type that hides nothing leaves the column empty.
    assert rows.get("header") == ""


def test_the_constraints_cell_leads_to_the_values_it_counts(browser, base):
    """Two links in a row lead to one page on purpose. The type name says what
    may be written; these words say that there are two of them, and a reader
    who does not yet know the first follows the second."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    opened = browser.evaluate(r"""
      var cells = document.querySelectorAll('#cd-detail .cd-holds');
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].textContent.trim() === '2 values') { cells[i].click(); return true; }
      }
      return false;
    """)
    assert opened, "no cell counting values was found"
    panel = browser.evaluate(PANEL)
    assert panel["heading"] == "cpacsType/mode"
    assert "Allowed values" in panel["text"]
    assert panel["values"] == ["inline-only", "second"]


def test_a_wildcard_is_visible_at_the_node_that_allows_it(browser, base):
    """It is not in the tree — it has no name and no instance path — so the
    node's own table is the only place a reader would meet it."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    row = browser.evaluate(r"""
      var rows = document.querySelectorAll('#cd-detail table tr');
      for (var i = 0; i < rows.length; i++) {
        var first = rows[i].children[0];
        if (first && first.textContent.indexOf('any') === 0) {
          var cells = [];
          for (var j = 0; j < rows[i].children.length; j++) {
            cells.push(rows[i].children[j].textContent.trim());
          }
          return cells;
        }
      }
      return null;
    """)
    assert row is not None, "the wildcard has no row"
    # Its own defaults, as XSD gives them where the schema is silent.
    assert row[1] == "##any"
    assert row[2] == "strict"
    assert row[5] == "Whatever a tool puts here."
    # And the reading of the word rides along on it.
    assert "An element the schema does not name may appear here." in row[0]


def test_the_rule_a_dataset_must_satisfy_is_shown_at_the_node(browser, base):
    """It hangs off the declaration, not off the type, so the node is the only
    place it can be read — there is no page for an element here."""
    browser.open(base + "/tree/cpacs/")
    browser.wait_for(READY, "the tree")
    table = browser.evaluate(r"""
      var heads = document.querySelectorAll('#cd-detail h2');
      for (var i = 0; i < heads.length; i++) {
        if (heads[i].textContent !== 'Identity constraints') continue;
        var rows = heads[i].nextElementSibling.querySelectorAll('tr');
        var out = [];
        for (var r = 0; r < rows.length; r++) {
          var cells = [];
          for (var c = 0; c < rows[r].children.length; c++) {
            cells.push(rows[r].children[c].textContent.trim());
          }
          out.push(cells);
        }
        return out;
      }
      return null;
    """)
    assert table is not None, "no identity constraints are shown"
    assert table[0] == ["Constraint", "Name", "Refers to", "Selector", "Fields"]
    assert table[1][1:] == ["nameKey", "", "./header", "name"]
    # The schema word carries its reading, as the compositors do.
    assert table[1][0].startswith("key")
    assert "may appear only once" in table[1][0]


def test_a_type_says_where_it_is_used(browser, base):
    """Built in the browser on the first type view, from the model it already
    has — the references in every type and the occurrences in the tree."""
    browser.open(base + "/tree/cpacs/header/")
    browser.wait_for(READY, "the tree")
    opened = browser.evaluate(r"""
      var buttons = document.querySelectorAll('#cd-detail .cd-crumb');
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.indexOf('headerType') !== -1) {
          buttons[i].click();
          return true;
        }
      }
      return false;
    """)
    assert opened, "the type could not be opened"
    used = browser.evaluate(r"""
      var box = document.querySelector('#cd-detail details.cd-usage');
      if (!box) return null;
      // Folded until asked: what is inside is only measured once it is open.
      var wasOpen = box.open;
      box.open = true;
      var table = box.querySelector('table');
      var heads = [];
      box.querySelectorAll('h3').forEach(function (h) {
        heads.push(h.textContent.replace(/\s+/g, ' ').trim());
      });
      return { section: true, closedByDefault: !wasOpen,
               items: table ? table.textContent.replace(/\s+/g, ' ').trim() : null,
               heads: heads };
    """)
    assert used is not None, "no Used by section"
    assert used["section"]
    assert used["closedByDefault"], "it is not what a reader came for"
    # `headerType` is the type of two children of the root in this fixture.
    assert "cpacsType" in used["items"]
    # The document first, then the schema.
    assert used["heads"] == ["In a dataset · 2 paths", "In the schema · 2 declarations"]


def test_the_path_count_shows_the_paths_it_counts(browser, base):
    """It used to jump to the first of them: the line said two and delivered
    one, choosing silently. A number that is clickable has to show what it
    counts."""
    browser.open(base + "/tree/cpacs/header/")
    browser.wait_for(READY, "the tree")
    browser.evaluate(r"""
      var buttons = document.querySelectorAll('#cd-detail .cd-crumb');
      for (var i = 0; i < buttons.length; i++) {
        if (buttons[i].textContent.indexOf('headerType') !== -1) { buttons[i].click(); return true; }
      }
      return false;
    """)
    listed = browser.evaluate(r"""
      var box = document.querySelector('#cd-detail details.cd-usage');
      box.open = true;
      var out = [];
      box.querySelectorAll('.cd-usage-list button').forEach(function (b) {
        out.push(b.textContent);
      });
      return out;
    """)
    assert listed == ["cpacs/header", "cpacs/wings"]

    # And each of them stands somewhere in the tree.
    browser.evaluate(
        "document.querySelectorAll('#cd-detail .cd-usage-list button')[1].click();"
        " return true;"
    )
    assert browser.evaluate(
        "return document.querySelector('#cd-detail h1').textContent;"
    ) == "wings"


def test_a_union_shows_its_members_where_the_node_stands(browser, base):
    """`systemTypeType` is the one union in CPACS 3.5.1, and the panel said
    `simpleType` and nothing else — the values sit in the members, one link on,
    and nothing pointed at them."""
    browser.open(base + "/tree/cpacs/systemType/")
    browser.wait_for(READY, "the tree")
    panel = browser.evaluate(PANEL)
    assert "Allowed types" in panel["text"]
    assert panel["values"] == ["ataChapterType", "xsd:string"]
    # The column beside them says what is behind the link before it is followed.
    assert "2 values" in panel["text"]
