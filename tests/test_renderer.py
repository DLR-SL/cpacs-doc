import json

import pytest
from lxml import etree

from cpacs_doc import renderer
from cpacs_doc.annotations import DDUE, SD, XLINK, XSD

NS = f'xmlns:ddue="{DDUE}" xmlns:xlink="{XLINK}"'


def parse(fragment: str):
    return etree.fromstring(f"<ddue:summary {NS}>{fragment}</ddue:summary>")


def render(fragment: str, **kwargs):
    context = renderer.RenderContext(**kwargs)
    return renderer.render(parse(fragment), context), context.findings


def test_paragraph_and_inline_markup():
    html, findings = render(
        "<ddue:para>A <ddue:legacyBold>bold</ddue:legacyBold> "
        "and <ddue:codeInline>coded</ddue:codeInline> line.</ddue:para>"
    )
    assert html == "<p>A <strong>bold</strong> and <code>coded</code> line.</p>"
    assert findings == []


def test_text_is_escaped():
    html, _ = render("<ddue:para>a &lt; b &amp; c</ddue:para>")
    assert html == "<p>a &lt; b &amp; c</p>"


def test_indentation_collapses_outside_code():
    html, _ = render("<ddue:para>one\n            two</ddue:para>")
    assert html == "<p>one two</p>"


def test_code_keeps_its_own_indentation():
    html, _ = render(
        '<ddue:code language="XML" title="Example">'
        "\n    &lt;wing&gt;\n        &lt;uID/&gt;\n    &lt;/wing&gt;\n</ddue:code>"
    )
    assert "&lt;wing&gt;\n    &lt;uID/&gt;" in html
    assert 'data-language="XML"' in html
    assert "<figcaption>Example</figcaption>" in html


def test_list_class_selects_the_tag():
    ordered, _ = render('<ddue:list class="ordered"><ddue:listItem>a</ddue:listItem></ddue:list>')
    assert ordered.startswith("<ol")
    bullet, _ = render('<ddue:list class="bullet"><ddue:listItem>a</ddue:listItem></ddue:list>')
    assert bullet.startswith("<ul")


def test_unknown_list_class_is_reported_not_guessed():
    html, findings = render('<ddue:list class="nowhere"><ddue:listItem>a</ddue:listItem></ddue:list>')
    assert html.startswith("<ul")
    assert [f.code for f in findings] == ["RENDER_LIST_CLASS_UNKNOWN"]


def test_no_header_row_is_inferred():
    """Two of thirteen tables in the schema mark a header; the rest do not."""
    html, _ = render(
        "<ddue:table><ddue:row><ddue:entry><ddue:legacyBold>Axis</ddue:legacyBold>"
        "</ddue:entry></ddue:row></ddue:table>"
    )
    assert "<th" not in html and "<thead" not in html
    assert "<td><strong>Axis</strong></td>" in html


def test_title_is_a_caption_inside_a_table_and_a_heading_outside():
    in_table, _ = render("<ddue:table><ddue:title>T</ddue:title></ddue:table>")
    assert "<caption>T</caption>" in in_table
    outside, _ = render("<ddue:section><ddue:title>T</ddue:title></ddue:section>")
    assert "<h3>T</h3>" in outside


def test_image_resolves_through_the_media_catalogue():
    media = {"fig": {"file": "figures/a.png", "alt": "An axis system"}}
    html, findings = render(
        '<ddue:mediaLink><ddue:image xlink:href="fig"/></ddue:mediaLink>',
        media=media,
        asset_prefix="/cpacs-doc",
    )
    assert 'src="/cpacs-doc/media/figures/a.png"' in html
    assert 'alt="An axis system"' in html
    assert findings == []


def test_unresolved_image_is_reported_and_leaves_a_marker():
    html, findings = render('<ddue:mediaLink><ddue:image xlink:href="gone"/></ddue:mediaLink>', media={})
    assert [f.code for f in findings] == ["RENDER_IMAGE_UNRESOLVED"]
    assert 'data-image-id="gone"' in html


def test_external_link_uses_uri_and_text():
    html, _ = render(
        "<ddue:externalLink><ddue:linkUri>https://cpacs.de</ddue:linkUri>"
        "<ddue:linkText>CPACS</ddue:linkText></ddue:externalLink>"
    )
    assert html == '<a class="cd-link" href="https://cpacs.de" rel="noopener">CPACS</a>'


def test_link_without_uri_is_reported():
    html, findings = render("<ddue:externalLink><ddue:linkText>CPACS</ddue:linkText></ddue:externalLink>")
    assert [f.code for f in findings] == ["RENDER_LINK_WITHOUT_URI"]
    assert "CPACS" in html


def test_unknown_element_is_reported_and_its_text_kept():
    html, findings = render("<ddue:para><ddue:blink>keep me</ddue:blink></ddue:para>")
    assert [f.code for f in findings] == ["RENDER_UNKNOWN_ELEMENT"]
    assert "keep me" in html


def test_definition_table():
    html, _ = render(
        "<ddue:definitionTable><ddue:definedTerm>Version</ddue:definedTerm>"
        "<ddue:definition>3.5</ddue:definition></ddue:definitionTable>"
    )
    assert "<dt>Version</dt><dd>3.5</dd>" in html


def test_none_renders_to_nothing():
    assert renderer.render(None, renderer.RenderContext()) == ""


def test_sandcastle_cross_reference_becomes_a_marked_span():
    """`xsd:xmlEntityReference` appears inside two documentation bodies. Its
    target is resolved by the generator, which knows the URL layout."""
    fragment = (
        f'<ddue:summary {NS} xmlns:xsd="{XSD}"><ddue:para>See '
        "<xsd:xmlEntityReference>Empty#T/wingType</xsd:xmlEntityReference>."
        "</ddue:para></ddue:summary>"
    )
    context = renderer.RenderContext()
    html = renderer.render(etree.fromstring(fragment), context)
    assert 'class="cd-xref" data-type="wingType"' in html
    assert context.findings == []


def test_unresolved_image_is_a_warning_when_no_catalogue_was_supplied():
    """`--no-media` is a deliberate choice; only a supplied catalogue that
    lacks the entry is an error."""
    _, findings = render('<ddue:mediaLink><ddue:image xlink:href="gone"/></ddue:mediaLink>')
    assert [(f.severity, f.code) for f in findings] == [("warning", "RENDER_IMAGE_UNRESOLVED")]
