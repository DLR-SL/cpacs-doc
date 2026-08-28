"""The general documentation: the sections of the root element's type.

In CPACS 3.5.1 that is 31 sections and 5,720 words hanging off `cpacsType` —
a handbook that, rendered as one fragment, can only be read by selecting the
root node and scrolling. Split, each section has a title, an address, a page
and a place in a list.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lxml import etree

from cpacs_doc import catalogue as catalogue_module
from cpacs_doc import content as content_module
from cpacs_doc import findings, generator, model as model_module
from cpacs_doc import tree as tree_module

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def built(tmp_path):
    """Model and report for the handbook fixture."""
    schema = tmp_path / "handbook.xsd"
    shutil.copyfile(FIXTURES / "handbook.xsd", schema)
    root = etree.parse(str(schema)).getroot()
    report = findings.Report()
    catalogue = catalogue_module.build(root, schema.name)
    report.extend(catalogue.findings)
    tree = tree_module.build(root, catalogue, schema.name)
    report.extend(tree.findings)
    content_by_type = {
        name: content_module.read(info, catalogue, schema.name)
        for name, info in catalogue.types.items()
    }
    for entry in content_by_type.values():
        report.extend(entry.findings)
    rendered, render_findings = model_module.render_all(
        catalogue, None, schema.name,
        sections_for=tree.root.type_name if tree.root else None,
    )
    report.extend(render_findings)
    model = model_module.build(
        catalogue, tree, None, report,
        schema_path=str(schema), schema_version=None,
        content_by_type=content_by_type, rendered=rendered,
    )
    return model, report


def codes(report) -> list[str]:
    return [finding.code for finding in report.findings]


def test_the_documentation_is_the_root_types_sections(built):
    model, _ = built
    documentation = model["documentation"]
    assert documentation["type"] == "cpacsType"
    assert [s["title"] for s in documentation["sections"]] == [
        "1. Overview", "2. Coordinate Systems", "Units", "units",
    ]


def test_the_address_is_mechanical_and_the_title_is_left_alone(built):
    """The chapter number stays in the title and in the address. Stripping it
    would leave the tool deciding which part of a heading means something."""
    model, _ = built
    sections = model["documentation"]["sections"]
    assert sections[0]["slug"] == "1-overview"
    assert sections[1]["slug"] == "2-coordinate-systems"


def test_two_titles_that_share_an_address_are_reported_not_merged(built):
    model, report = built
    slugs = [s["slug"] for s in model["documentation"]["sections"]]
    assert slugs[2:] == ["units", "units-2"]
    assert "SECTION_ADDRESS_TAKEN" in codes(report)


def test_a_section_without_a_title_stays_in_the_body_and_is_reported(built):
    """It has no name to be listed under, and lifting it out would lose it."""
    model, report = built
    titles = [s["title"] for s in model["documentation"]["sections"]]
    assert "" not in titles
    remarks = model["types"]["cpacsType"]["documentation"]["remarksHtml"]
    assert "An aside with no title of its own." in remarks
    assert "SECTION_WITHOUT_TITLE" in codes(report)


def test_the_lifted_sections_leave_the_remarks_body(built):
    """Otherwise the same prose would sit in two places and drift apart."""
    model, _ = built
    remarks = model["types"]["cpacsType"]["documentation"]["remarksHtml"]
    assert "Where the axes point." not in remarks
    # What surrounded them stays: the version table heads the index page.
    assert "3.5.1" in remarks


def test_the_section_body_does_not_repeat_its_own_title(built):
    """The title heads the page and the list entry."""
    model, _ = built
    overview = model["documentation"]["sections"][0]
    assert "What the dataset is for." in overview["html"]
    assert "1. Overview" not in overview["html"]


def test_a_schema_without_sections_carries_no_documentation_key(tmp_path):
    schema = tmp_path / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)
    root = etree.parse(str(schema)).getroot()
    report = findings.Report()
    catalogue = catalogue_module.build(root, schema.name)
    tree = tree_module.build(root, catalogue, schema.name)
    rendered, _ = model_module.render_all(
        catalogue, None, schema.name,
        sections_for=tree.root.type_name if tree.root else None,
    )
    model = model_module.build(
        catalogue, tree, None, report,
        schema_path=str(schema), schema_version=None, rendered=rendered,
    )
    assert model["documentation"] == {}


def test_every_section_becomes_a_citable_page(built, tmp_path):
    model, _ = built
    output = tmp_path / "site"
    result = generator.generate(model, output)
    assert result.docs == 4
    assert (output / "doc" / "index.html").exists()
    for slug in ("1-overview", "2-coordinate-systems", "units", "units-2"):
        page = output / "doc" / slug / "index.html"
        assert page.exists(), slug
    page = (output / "doc" / "2-coordinate-systems" / "index.html").read_text(encoding="utf-8")
    assert "<h1>2. Coordinate Systems</h1>" in page
    assert "Where the axes point." in page
    # Two levels down, like a type page, so the stylesheet resolves.
    assert '"../../assets/styles.css"' in page


def test_the_index_lists_the_sections_in_document_order(built, tmp_path):
    model, _ = built
    output = tmp_path / "site"
    generator.generate(model, output)
    index = (output / "doc" / "index.html").read_text(encoding="utf-8")
    order = [index.index(title) for title in ("1. Overview", "2. Coordinate Systems", "Units")]
    assert order == sorted(order)
    # What the body held besides its sections heads the index rather than
    # being dropped.
    assert "3.5.1" in index


def test_the_type_the_documentation_hangs_off_links_to_it(built, tmp_path):
    """Without the list its page would read as though the documentation had
    been lost: the sections are pages of their own now."""
    model, _ = built
    output = tmp_path / "site"
    generator.generate(model, output)
    page = (output / "type" / "cpacsType" / "index.html").read_text(encoding="utf-8")
    assert "../../doc/1-overview/index.html" in page
    other = (output / "type" / "headerType" / "index.html").read_text(encoding="utf-8")
    assert "doc/" not in other


def test_the_root_index_offers_the_documentation(built, tmp_path):
    model, _ = built
    output = tmp_path / "site"
    generator.generate(model, output)
    index = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="doc/index.html"' in index


def test_the_viewer_shell_carries_the_tabs_and_the_pane(built, tmp_path):
    model, _ = built
    output = tmp_path / "site"
    generator.generate(model, output)
    html = (output / "404.html").read_text(encoding="utf-8")
    assert 'role="tablist"' in html
    assert ">Tree</button>" in html and ">Handbook</button>" in html
    assert 'id="cd-docs"' in html
