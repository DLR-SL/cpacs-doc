import json

import pytest

from cpacs_doc import generator


@pytest.fixture
def model():
    return {
        "meta": {"schemaVersion": "3.5.1"},
        "statistics": {"types": 2, "distinctPaths": 4, "maxDepth": 2},
        "types": {
            "wingType": {
                "name": "wingType",
                "kind": "complexType",
                "base": "baseType",
                "derivation": "extension",
                "compositor": "sequence",
                "line": 42,
                "documentation": {
                    "summaryHtml": "<p>A wing.</p>",
                    "remarksHtml": '<img class="cd-image" src="%ROOT%/media/figures/a.png" alt="A">'
                    '<span class="cd-xref" data-type="baseType">baseType</span>'
                    '<span class="cd-xref" data-type="goneType">goneType</span>',
                },
                "attributes": [
                    {"name": "uID", "type": "xsd:ID", "use": "required", "inherited": False,
                     "declaredIn": "wingType", "line": 43},
                    {"name": "ext", "type": "xsd:string", "use": "optional", "inherited": True,
                     "declaredIn": "baseType", "line": 12},
                ],
                "children": [
                    {"kind": "group", "compositor": "sequence", "minOccurs": 1, "maxOccurs": 1,
                     "members": [
                         {"kind": "element", "name": "span", "type": "xsd:double",
                          "minOccurs": 1, "maxOccurs": 1},
                         {"kind": "group", "compositor": "choice", "minOccurs": 0, "maxOccurs": 1,
                          "members": [
                              {"kind": "element", "name": "segment", "type": "baseType",
                               "minOccurs": 0, "maxOccurs": None},
                          ]},
                     ]},
                ],
            },
            "nacaType/code": {
                "name": "nacaType/code",
                "kind": "simpleType",
                "line": 99,
                "documentation": {},
                "enumeration": [{"value": "0012", "documentation": {"text": "symmetric"}}],
            },
            "markingType": {
                "name": "markingType",
                "kind": "simpleType",
                "line": 7,
                "documentation": {},
                "union": ["nacaType/code", "xsd:string"],
            },
            "baseType": {"name": "baseType", "kind": "complexType", "line": 1, "documentation": {}},
        },
        "media": {},
    }


def test_a_page_is_written_per_type(model, tmp_path):
    result = generator.generate(model, tmp_path)
    assert result.pages == 4
    assert (tmp_path / "type" / "wingType" / "index.html").exists()
    assert (tmp_path / "index.html").exists()


def test_slash_in_an_anonymous_type_name_becomes_a_directory_safe_slug(model, tmp_path):
    generator.generate(model, tmp_path)
    assert (tmp_path / "type" / "nacaType--code" / "index.html").exists()
    assert generator.unslug(generator.slug("nacaType/code")) == "nacaType/code"


def test_the_type_index_marks_a_break_after_the_slash(model, tmp_path):
    """A type name carries no space, so the long ones were drawn over the
    column beside them. The slash is the one place a reader still takes the
    name for one name, and the line-breaking algorithm offers nothing there."""
    generator.generate(model, tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert ">nacaType/<wbr>code</a>" in index
    assert ">wingType</a>" in index


def test_type_links_point_at_sibling_pages(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'href="../baseType/index.html"' in html
    assert 'href="../../baseType' not in html


def test_a_builtin_type_has_no_page_here_and_points_at_its_reference(model, tmp_path):
    """`xsd:ID` is not in the schema, so there is nothing to write a page from —
    and a reader who wants to know what it allows had to leave the
    documentation to find out. The reference is where that answer is."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "<code>xsd:ID</code>" in html
    assert 'href="../xsd:ID' not in html
    assert generator.BUILTIN_REFERENCE + "ID.html" in html
    # It leaves the site, so it does not take the reader's place with it.
    assert 'target="_blank"' in html


def test_a_name_that_is_not_a_builtin_stays_text(model, tmp_path):
    """The reference documents the built-in types of XSD 1.0 and no more. An
    address derived for anything else would be a guess, and a dead link is
    worse than a word."""
    model["types"]["wingType"]["attributes"][0]["type"] = "xsd:notADatatype"
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "<code>xsd:notADatatype</code>" in html
    assert "notADatatype.html" not in html
    assert generator.builtin_reference("xsd:notADatatype") == ""
    # The ones it does document keep their capitals in the address.
    assert generator.builtin_reference("xsd:dateTime").endswith("t-xsd_dateTime.html")


def test_root_placeholder_is_resolved_against_page_depth(model, tmp_path):
    """The same fragment is used by pages at different depths, so the renderer
    leaves a placeholder rather than a path."""
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'src="../../media/figures/a.png"' in page
    assert generator.ROOT_TOKEN not in page
    assert generator.ROOT_TOKEN not in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_cross_references_resolve_to_links_and_unknown_targets_stay_text(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'href="../baseType/index.html"><code>baseType</code>' in html
    assert "<code>goneType</code>" in html
    assert "cd-xref" not in html


def test_a_type_page_links_back_into_the_tree(model, tmp_path):
    """Someone arriving from a cited URL otherwise has no route into the
    structure."""
    model["firstPaths"] = {"wingType": "cpacs/wings/wing"}
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'href="../../tree/cpacs/wings/wing/"' in html
    assert "Show in tree" in html


def test_a_type_with_no_tree_occurrence_gets_no_such_link(model, tmp_path):
    """106 anonymous inline types never appear as an element's type."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "nacaType--code" / "index.html").read_text(encoding="utf-8")
    assert "Show in tree" not in html


def test_a_group_heads_its_members_instead_of_repeating_per_row(model, tmp_path):
    """A compositor governs a set of children, so it is a row of its own. The
    schema word stays for readers who think in it, with a plain reading next to
    it for those who do not."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert '<span class="cd-group-term" tabindex="0">sequence' in html
    assert "must appear in exactly this order" in html
    assert "cd-group-sequence" in html


def test_the_explanation_is_focusable_not_hover_only(model, tmp_path):
    """A hover-only tooltip is unreachable by keyboard and on touch."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'class="cd-group-term" tabindex="0"' in html
    assert 'class="cd-tip" role="note"' in html


def test_an_optional_group_states_its_own_occurrence(model, tmp_path):
    """14 of the 84 choice groups are optional as a whole; that belongs on the
    group, not on its members."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "Exactly one of the alternatives" in html
    assert "[0..1]</span> optional" in html


def test_nested_members_carry_their_depth(model, tmp_path):
    """Depth travels as a custom property so one CSS rule draws the guides for
    any nesting level."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'class="cd-indent" style="--depth:1"' in html
    assert 'class="cd-indent" style="--depth:2"' in html


def test_bare_schema_line_is_not_shown(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "Schema line" not in html


def test_occurrence_states_the_bounds_and_reads_them(model, tmp_path):
    """`0…1` alone was neither the schema's own words nor anybody's plain
    reading, and 3,184 of the 3,663 declarations in CPACS 3.5.1 say one of two
    things. Both are here: the bounds for whoever reads them faster than a
    sentence, the reading for whoever does not."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "[0..∞]</span> any number" in html
    assert "[1..1]</span> required" in html
    # and the column heading says where the schema writes the same thing
    assert "minOccurs and maxOccurs" in html


def test_a_bounded_range_keeps_its_numbers(model, tmp_path):
    """20 of the 3,663 declarations are neither of the four common cases; a
    vocabulary that swallowed their bounds would be a lie, not a reading."""
    words = generator._occurrence_words
    assert words({"minOccurs": 2, "maxOccurs": None}) == "2 or more"
    assert words({"minOccurs": 1, "maxOccurs": 2}) == "1 to 2"
    assert words({"minOccurs": 0, "maxOccurs": 2}) == "up to 2"
    assert words({"minOccurs": 3, "maxOccurs": 3}) == "exactly 3"
    # the declaration that says nothing means exactly one
    assert words({}) == "required"


def test_bounds_nobody_has_a_phrase_for_are_left_to_the_notation(model, tmp_path):
    """The schema may grow a combination this file has no English for. The
    bounds are exact whatever they are; a phrase invented to fill the gap would
    not be, so the cell then carries the notation alone."""
    assert generator._occurrence_words({"minOccurs": 0, "maxOccurs": 0}) == ""
    assert generator._occurrence({"minOccurs": 0, "maxOccurs": 0}) == (
        '<span class="cd-bounds">[0..0]</span>'
    )
    assert generator._notation({"minOccurs": 7, "maxOccurs": None}) == "[7..∞]"


def test_attribute_table_does_not_name_the_declaring_type(model, tmp_path):
    """The column answered a question the reader was not asking.

    `inherited` and `declaredIn` stay in the model; only the column is gone.
    """
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    section = html.split('<section class="cd-attributes"')[1].split("</section>")[0]
    assert "Inherited from" not in html and "baseType" not in section


def test_a_union_lists_its_members_and_what_they_hold(model, tmp_path):
    """The page of a union carries nothing of its own; what may be written
    there is a link further on, and the reader has to be told there is one."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "markingType" / "index.html").read_text(encoding="utf-8")
    assert "Allowed types" in html and ">union<" in html
    assert f'href="../{generator.slug("nacaType/code")}/index.html"' in html
    assert "1 value" in html
    assert "<code>xsd:string</code>" in html


def test_a_row_pointing_at_a_union_says_there_is_one(model, tmp_path):
    """Without this the row reads as a plain string with nothing behind it —
    which is what hid the values in the first place."""
    model["types"]["wingType"]["children"][0]["members"][0]["type"] = "markingType"
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "one of 2 types" in html


def test_missing_media_root_is_reported_not_silent(model, tmp_path):
    model["media"] = {"a": {"file": "figures/a.png", "alt": "A"}}
    result = generator.generate(model, tmp_path)
    assert [f.code for f in result.findings] == ["GENERATOR_MEDIA_ROOT_MISSING"]


def test_media_files_are_copied(model, tmp_path):
    source = tmp_path / "src" / "figures"
    source.mkdir(parents=True)
    (source / "a.png").write_bytes(b"x")
    model["media"] = {"a": {"file": "figures/a.png", "alt": "A"}}
    out = tmp_path / "out"
    result = generator.generate(model, out, media_root=tmp_path / "src")
    assert result.assets == 1
    assert (out / "media" / "figures" / "a.png").exists()


def test_router_is_written_with_stylesheet_and_script_inlined(model, tmp_path):
    """404.html is served from arbitrary depth and cannot resolve a relative
    URL, nor does it know its root before the script has run."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert "<style>" in html and "<script>" in html
    assert 'href="' not in html.split("<script>")[0].split("<style>")[0]
    assert 'id="cd-tree"' in html and 'id="cd-detail"' in html


def test_the_panes_carry_what_keyboard_operation_needs(model, tmp_path):
    """The detail panel can be focused, so Enter in the tree has somewhere to
    go (F1, N13). The tree role itself belongs to the rows' own container,
    which the viewer builds — the pane is a tab panel."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert 'id="cd-tree"' in html
    assert 'id="cd-detail" class="cd-pane cd-pane-detail" tabindex="-1"' in html
    # The keys cannot be read off the tree, so there is a way to ask for them.
    assert 'id="cd-help"' in html


def test_every_page_can_set_the_palette_before_it_is_painted(model, tmp_path):
    """The choice is stored per browser and applied by a script inline in the
    page. It has to come before the stylesheet, or the wrong palette is painted
    first and corrected afterwards."""
    generator.generate(model, tmp_path)
    # The router inlines its stylesheet, the pages link theirs.
    for name, sheet in (("404.html", "<style>"),
                        ("index.html", "styles.css"),
                        ("type/wingType/index.html", "styles.css")):
        html = (tmp_path / name).read_text(encoding="utf-8")
        assert "cpacs-doc.theme" in html, name
        assert html.index("cpacs-doc.theme") < html.index(sheet), name
    # The control itself sits on the pages as well as in the viewer, so a
    # reader who arrives by citation is not stuck with what the system says.
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'id="cd-theme"' in page


def test_assets_are_written_as_files_for_the_static_pages(model, tmp_path):
    generator.generate(model, tmp_path)
    assert (tmp_path / "assets" / "styles.css").exists()
    assert (tmp_path / "assets" / "viewer.js").exists()


def test_router_keeps_the_root_placeholder_for_run_time_substitution(model, tmp_path):
    """Unlike a static page, the router resolves the placeholder in the browser,
    once it has derived its own root from the requested path."""
    generator.generate(model, tmp_path)
    script = (tmp_path / "assets" / "viewer.js").read_text(encoding="utf-8")
    assert generator.ROOT_TOKEN in script


def test_an_anonymous_type_is_labelled_by_its_base_and_still_linked(model, tmp_path):
    """The synthetic name says where the type was declared, which the row it
    sits in has just said; the base says what may be written there. The link is
    what makes the values reachable at all, so it stays."""
    model["types"]["wingType/mode"] = {
        "name": "wingType/mode", "kind": "simpleType", "anonymous": True,
        "base": "xsd:string", "derivation": "restriction", "line": 7,
        "documentation": {}, "enumeration": [{"value": "inline-only"}],
    }
    model["types"]["wingType"]["children"][0]["members"].append(
        {"kind": "element", "name": "mode", "type": "wingType/mode",
         "minOccurs": 0, "maxOccurs": 1}
    )
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "wingType/mode" not in page, "the synthetic name has no business in a table"
    assert '<a href="../wingType--mode/index.html"><code>xsd:string</code>' in page
    # And the row says there is something behind the link: `xsd:string` alone
    # reads like the plain string in the row above it.
    # …and says so in words that name what is there, linked to the same page:
    # a reader who does not know that a type name holds values follows these.
    assert ('<a class="cd-holds" href="../wingType--mode/index.html">1 value</a>'
            in page)
    values = (tmp_path / "type" / "wingType--mode" / "index.html").read_text(encoding="utf-8")
    assert "inline-only" in values


def test_value_constraints_are_shown_with_the_schema_word_and_its_reading(model, tmp_path):
    """The schema word stays in the table, as it does for compositors, and the
    plain reading rides along on it."""
    model["types"]["wingType"]["facets"] = [
        {"name": "minInclusive", "value": "0"},
        {"name": "pattern", "value": "[0-9]{4}"},
    ]
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "<h2>Value constraints</h2>" in page
    assert "minInclusive" in page and "<code>0</code>" in page
    assert "The value must be this or greater." in page
    assert "The value must match this regular expression." in page
    # Reachable without a pointer, like every other explanation on these pages.
    assert '<span class="cd-facet" tabindex="0">' in page


def test_every_table_stands_in_a_scroller_of_its_own(model, tmp_path):
    """A reference table is as wide as its widest name, so it cannot be made to
    fit the reading measure — and where it had no container of its own it was
    the page that scrolled, taking the heading and the breadcrumb with it. What
    that looks like in a browser is measured in test_page_tables."""
    model["types"]["wingType"]["facets"] = [{"name": "pattern", "value": "[0-9]{4}"}]
    generator.generate(model, tmp_path)
    for name in ("wingType", "nacaType--code", "markingType"):
        page = (tmp_path / "type" / name / "index.html").read_text(encoding="utf-8")
        assert "<table" in page, name
        assert "<table" not in page.replace('<div class="cd-scroll"><table', ""), name


def test_a_type_without_constraints_gets_no_table(model, tmp_path):
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "Value constraints" not in page


def test_a_child_shows_what_it_is_worth_unwritten(model, tmp_path):
    members = model["types"]["wingType"]["children"][0]["members"]
    members.append({"kind": "element", "name": "ratio", "type": "xsd:double",
                    "minOccurs": 0, "maxOccurs": 1, "default": "0.5"})
    members.append({"kind": "element", "name": "unit", "type": "xsd:string",
                    "minOccurs": 0, "maxOccurs": 1, "fixed": "m"})
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    children = page.split("<h2>Child elements</h2>")[1]
    assert "<th>Default</th>" in children
    assert "<code>0.5</code>" in children
    # A fixed value is not a default, and the column says so.
    assert '<code>m</code> <span class="cd-fixed">fixed</span>' in children


def test_the_kind_line_names_the_value_where_the_base_does_not(model, tmp_path):
    model["types"]["wingType"]["contentType"] = "xsd:double"
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "<code>xsd:double</code>" in page
    assert "value <a" in page and generator.BUILTIN_REFERENCE + "double.html" in page


def test_the_kind_line_does_not_say_the_base_twice(model, tmp_path):
    """`doubleBaseType` extends `xsd:double`: the base has already said it."""
    model["types"]["wingType"]["base"] = "xsd:double"
    model["types"]["wingType"]["contentType"] = "xsd:double"
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "value <code>" not in page


def test_a_wildcard_gets_a_row_saying_what_it_allows(model, tmp_path):
    """It has no name and no type, so the row says what it does allow: a
    namespace, how strictly it is checked, and its own documentation."""
    model["types"]["wingType"]["children"][0]["members"].append({
        "kind": "any", "namespace": "##other", "processContents": "lax",
        "minOccurs": 0, "maxOccurs": 1,
        "documentation": {"text": "Anything from elsewhere."},
    })
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    children = page.split("<h2>Child elements</h2>")[1]
    assert "<code>##other</code>" in children
    assert "lax" in children
    assert "Anything from elsewhere." in children
    # The schema word carries its reading, as a compositor does.
    assert "An element the schema does not name may appear here." in children


def test_usage_is_derived_from_what_the_model_already_holds(model):
    """Storing it would be 8.3 MB of instance paths beside a 4.2 MB model, and
    both facts are in there already — the references in every type, the
    occurrences in the tree."""
    model["tree"] = {"d": "0", "children": [{"d": "1"}, {"d": "1"}]}
    model["declarations"] = {
        "0": {"name": "cpacs", "type": "wingType"},
        "1": {"name": "wing", "type": "baseType"},
    }
    usage = generator.usage_index(model)
    assert usage["counts"]["wingType"] == 1
    assert usage["counts"]["baseType"] == 2
    # And the paths themselves, up to the cap: where a type stands in a
    # document is the answer a reader wants first.
    assert usage["paths"]["baseType"] == ["cpacs/wing", "cpacs/wing"]
    assert ("wingType", "span") in usage["users"]["xsd:double"]
    assert ("wingType", "segment") in usage["users"]["baseType"]
    # Attributes name types too, and the list says which attribute it was.
    assert ("wingType", "@uID") in usage["users"]["xsd:ID"]


def test_the_used_by_section_names_the_declarations_and_counts_the_paths(model, tmp_path):
    model["tree"] = {"d": "0", "children": [{"d": "1"}, {"d": "1"}]}
    model["declarations"] = {
        "0": {"name": "cpacs", "type": "wingType"},
        "1": {"name": "wing", "type": "baseType"},
    }
    model["firstPaths"] = {"baseType": "cpacs/wing"}
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "baseType" / "index.html").read_text(encoding="utf-8")
    assert "<h2>Used by</h2>" in page
    assert '<a href="../wingType/index.html"><code>wingType</code></a>' in page
    assert "<code>segment</code>" in page
    # Stated, not linked: a page cannot show 28,120 paths, and a link to the
    # first would promise the count and deliver one. The way in is the
    # "Show in tree" link at the head of the page.
    usage = page.split('<section class="cd-usage">')[1]
    # Shown, not folded: the paths are the one answer neither predecessor could
    # give, and a click at every type to reach them is a click too many.
    assert "<details" not in usage
    # The document first, then the schema: the headings name the level, since
    # both lists are elements.
    assert usage.index("In a dataset") < usage.index("In the schema")
    assert "· 2 paths" in usage
    assert '<a href="../../tree/cpacs/wing/"><code>cpacs/wing</code></a>' in usage
    assert "<th>Type</th><th>Name</th>" in usage


def test_a_type_used_everywhere_gets_a_count_rather_than_a_list(model, tmp_path):
    """`doubleBaseType` is named by 673 declarations and sits at 28,120 paths.
    A list of either says nothing a number does not."""
    members = model["types"]["wingType"]["children"][0]["members"]
    for i in range(30):
        members.append({"kind": "element", "name": f"field{i}", "type": "baseType",
                        "minOccurs": 0, "maxOccurs": 1})
    generator.generate(model, tmp_path)
    page = (tmp_path / "type" / "baseType" / "index.html").read_text(encoding="utf-8")
    assert "and 6 more" in page, "31 users, 25 shown"


# ---- the one-file form ----
#
# What `--site` spreads over 1,341 files, `--single` puts into one that opens
# from a disk. The properties that makes it need are all about being read
# without a server: nothing may be fetched, and nothing may be linked that is
# not in the file.


def model_payload(html: str) -> dict:
    """The model back out of the document, the way the viewer reads it."""
    opening = f'<script type="application/json" id="{generator.MODEL_ELEMENT}">'
    start = html.index(opening) + len(opening)
    return json.loads(html[start:html.index("</script>", start)])


def test_one_file_carries_the_whole_model(model, tmp_path):
    result = generator.generate_single(model, tmp_path)
    assert result.pages == 1
    html = (tmp_path / generator.SINGLE_NAME).read_text(encoding="utf-8")
    assert model_payload(html) == model
    # The viewer and its stylesheet travel in the same document, as they do in
    # the router page this is built from.
    assert "cd-app" in html and "function parseLocation" in html


def test_the_deployed_router_carries_no_model(model, tmp_path):
    """Its model is fetched from a known address, and the presence of an
    inlined one is what tells the viewer it is being read from a disk."""
    generator.generate(model, tmp_path)
    router = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert f'id="{generator.MODEL_ELEMENT}"' not in router


def test_documentation_cannot_close_the_element_it_is_carried_in(model, tmp_path):
    """A fragment holding "</script>" would end the block early and leave the
    rest of the model in the page as text. Escaping "<" is what prevents it,
    and the model must survive the escaping unchanged."""
    model["types"]["wingType"]["documentation"]["remarksHtml"] = (
        "<p>An example: &lt;/script&gt; and </script> inside.</p>"
    )
    generator.generate_single(model, tmp_path)
    html = (tmp_path / generator.SINGLE_NAME).read_text(encoding="utf-8")
    assert model_payload(html) == model
    # Three script elements: the theme, the model, the viewer. No fourth end
    # tag from the model's own content.
    assert html.count("</script>") == 3


def test_a_figure_is_embedded_rather_than_referenced(model, tmp_path):
    media_root = tmp_path / "figures"
    (media_root / "figures").mkdir(parents=True)
    (media_root / "figures" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n0123456789")
    model["media"] = {"a": {"file": "figures/a.png", "alt": "A"}}

    result = generator.generate_single(model, tmp_path, media_root=media_root)

    assert result.assets == 1
    html = (tmp_path / generator.SINGLE_NAME).read_text(encoding="utf-8")
    assert "data:image/png;base64," in html
    # Nothing is left that would go looking for a directory beside the file.
    assert generator.ROOT_TOKEN + "/media/" not in html


def test_a_figure_no_documentation_mentions_is_left_out(model, tmp_path):
    """The file is loaded whole, so an unreferenced catalogue entry is weight
    and nothing else — 14 of the 98 in CPACS 3.5.1."""
    media_root = tmp_path / "figures"
    (media_root / "figures").mkdir(parents=True)
    (media_root / "figures" / "unused.png").write_bytes(b"\x89PNG\r\n\x1a\n0123456789")
    model["media"] = {"unused": {"file": "figures/unused.png", "alt": "U"}}

    result = generator.generate_single(model, tmp_path, media_root=media_root)

    assert result.assets == 0
    html = (tmp_path / generator.SINGLE_NAME).read_text(encoding="utf-8")
    assert "base64" not in json.dumps(model_payload(html))


def test_a_figure_that_is_referenced_but_missing_is_reported(model, tmp_path):
    model["media"] = {"a": {"file": "figures/a.png", "alt": "A"}}
    result = generator.generate_single(model, tmp_path, media_root=tmp_path / "nowhere")
    assert result.assets == 0
    assert [f.code for f in result.findings] == ["GENERATOR_MEDIA_MISSING"]


def test_without_a_media_root_the_figures_are_reported_rather_than_dropped(model, tmp_path):
    model["media"] = {"a": {"file": "figures/a.png", "alt": "A"}}
    result = generator.generate_single(model, tmp_path)
    assert [f.code for f in result.findings] == ["GENERATOR_MEDIA_ROOT_MISSING"]
