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
            "baseType": {"name": "baseType", "kind": "complexType", "line": 1, "documentation": {}},
        },
        "media": {},
    }


def test_a_page_is_written_per_type(model, tmp_path):
    result = generator.generate(model, tmp_path)
    assert result.pages == 3
    assert (tmp_path / "type" / "wingType" / "index.html").exists()
    assert (tmp_path / "index.html").exists()


def test_slash_in_an_anonymous_type_name_becomes_a_directory_safe_slug(model, tmp_path):
    generator.generate(model, tmp_path)
    assert (tmp_path / "type" / "nacaType--code" / "index.html").exists()
    assert generator.unslug(generator.slug("nacaType/code")) == "nacaType/code"


def test_type_links_point_at_sibling_pages(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert 'href="../baseType/index.html"' in html
    assert 'href="../../baseType' not in html


def test_builtin_types_are_not_linked(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "<code>xsd:ID</code>" in html
    assert 'href="../xsd:ID' not in html


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
    assert '<span class="cd-group-term">sequence</span>' in html
    assert "in this order" in html
    assert "cd-group-sequence" in html


def test_an_optional_group_states_its_own_occurrence(model, tmp_path):
    """14 of the 84 choice groups are optional as a whole; that belongs on the
    group, not on its members."""
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "exactly one of · 0…1" in html


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


def test_unbounded_cardinality_is_shown(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "0…∞" in html


def test_inherited_attributes_name_their_origin(model, tmp_path):
    generator.generate(model, tmp_path)
    html = (tmp_path / "type" / "wingType" / "index.html").read_text(encoding="utf-8")
    assert "cd-inherited" in html and "baseType" in html


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
