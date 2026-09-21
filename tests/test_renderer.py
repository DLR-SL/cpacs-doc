import json
import re
from html import unescape

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


def test_subscript_and_superscript():
    html, findings = render(
        "<ddue:para>R<ddue:subscript>LE</ddue:subscript>/c = "
        "B<ddue:subscript>0</ddue:subscript><ddue:superscript>2</ddue:superscript>/2</ddue:para>"
    )
    assert html == "<p>R<sub>LE</sub>/c = B<sub>0</sub><sup>2</sup>/2</p>"
    assert findings == []


def test_tigl_alert_is_a_labelled_aside():
    """A note on how TiGL treats the data, kept apart from the tool-neutral text."""
    html, findings = render(
        '<ddue:alert class="tigl"><ddue:para>TiGL 3.5 counts from 0.</ddue:para></ddue:alert>'
    )
    assert html == (
        '<aside class="cd-alert cd-alert-tigl" role="note">'
        '<p class="cd-alert-label">TiGL</p><p>TiGL 3.5 counts from 0.</p></aside>'
    )
    assert findings == []


def test_note_alert():
    html, findings = render('<ddue:alert class="note"><ddue:para>Mind the sign.</ddue:para></ddue:alert>')
    assert html.startswith('<aside class="cd-alert cd-alert-note" role="note"><p class="cd-alert-label">Note</p>')
    assert findings == []


def test_unknown_alert_class_is_reported_and_rendered_as_note():
    html, findings = render('<ddue:alert class="danger"><ddue:para>x</ddue:para></ddue:alert>')
    assert 'class="cd-alert cd-alert-note"' in html
    assert [f.code for f in findings] == ["RENDER_ALERT_CLASS_UNKNOWN"]


def test_text_is_escaped():
    html, _ = render("<ddue:para>a &lt; b &amp; c</ddue:para>")
    assert html == "<p>a &lt; b &amp; c</p>"


def test_indentation_collapses_outside_code():
    html, _ = render("<ddue:para>one\n            two</ddue:para>")
    assert html == "<p>one two</p>"


def plain(html: str) -> str:
    """The block's text, with the marks the highlighter added taken back off."""
    return unescape(re.sub(r"</?span[^>]*>", "", html))


def test_code_keeps_its_own_indentation():
    html, _ = render(
        '<ddue:code language="XML" title="Example">'
        "\n    &lt;wing&gt;\n        &lt;uID/&gt;\n    &lt;/wing&gt;\n</ddue:code>"
    )
    assert "<wing>\n    <uID/>" in plain(html)
    assert 'data-language="XML"' in html
    assert "<figcaption>Example</figcaption>" in html


def test_the_parts_of_an_xml_example_are_marked():
    """An example is read for which words are elements, which are attributes
    and which are values. Set in one colour they are a wall of text."""
    html, _ = render(
        '<ddue:code language="XML">'
        "&lt;wing uID=&quot;w1&quot;&gt;text&lt;/wing&gt; &lt;!-- a note --&gt;"
        "</ddue:code>"
    )
    assert '<span class="cd-tag">wing</span>' in html
    assert '<span class="cd-attr">uID</span>' in html
    assert '<span class="cd-value">&quot;w1&quot;</span>' in html
    assert '<span class="cd-comment">&lt;!-- a note --&gt;</span>' in html
    # Text between the tags is text, and the marks add nothing to it.
    assert "&gt;text&lt;" in html.replace('<span class="cd-punct">', "").replace(
        "</span>", ""
    )


def test_highlighting_changes_no_character_of_the_source():
    """The block is the schema's own words. 13 of the 50 in CPACS 3.5.1 are
    excerpts with `...` in them and would not parse; marking them must not
    repair, reorder or drop anything."""
    source = '<a b="1" c=\'2\'>x &amp; y</a>\n<?pi?>\n<!-- open'
    assert plain(renderer._highlight_xml(source)) == source


def test_an_unrecognised_language_is_left_alone():
    html, _ = render(
        '<ddue:code language="Python">print(1)</ddue:code>'
    )
    assert "<span" not in html and "print(1)" in html


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
    assert '<code class="cd-xref" data-type="wingType">wingType</code>' in html
    assert context.findings == []


def test_unresolved_image_is_a_warning_when_no_catalogue_was_supplied():
    """`--no-media` is a deliberate choice; only a supplied catalogue that
    lacks the entry is an error."""
    _, findings = render('<ddue:mediaLink><ddue:image xlink:href="gone"/></ddue:mediaLink>')
    assert [(f.severity, f.code) for f in findings] == [("warning", "RENDER_IMAGE_UNRESOLVED")]


# --- Cross references -------------------------------------------------------
#
# Two ways into the same marker. A type name written as `ddue:codeInline` is a
# reference to that type and is recognised without the author doing anything
# (243 of them in CPACS 3.5.1); `ddue:link` is what an author writes where the
# name alone is not the reference — a different wording, or a target the rule
# cannot see. Neither resolves here: the renderer records the target and the
# generator, which knows the URL layout, turns it into an anchor.

CATALOGUE = frozenset({"wingType", "wingSectionType"})


def test_a_type_name_in_code_inline_becomes_a_cross_reference():
    html, findings = render(
        "<ddue:para>Its airfoils sit in a <ddue:codeInline>wingSectionType</ddue:codeInline>.</ddue:para>",
        type_names=CATALOGUE,
    )
    assert html == (
        '<p>Its airfoils sit in a <code class="cd-xref" '
        'data-type="wingSectionType">wingSectionType</code>.</p>'
    )
    assert findings == []


def test_code_inline_that_names_no_type_stays_plain_code():
    """Element names, attribute values and literals are `codeInline` too, and
    63% of the occurrences in CPACS 3.5.1 are one of those."""
    html, findings = render(
        "<ddue:para>The <ddue:codeInline>sections</ddue:codeInline> of a wing.</ddue:para>",
        type_names=CATALOGUE,
    )
    assert html == "<p>The <code>sections</code> of a wing.</p>"
    assert findings == []


def test_without_a_catalogue_nothing_is_linked_automatically():
    """No catalogue is a deliberate choice by the caller, as with the media
    entries — not a reference that failed to resolve."""
    html, findings = render("<ddue:para><ddue:codeInline>wingType</ddue:codeInline></ddue:para>")
    assert html == "<p><code>wingType</code></p>"
    assert findings == []


def test_code_inline_holding_markup_is_not_a_reference():
    """The rule reads the text as written. Anything with structure inside it is
    not a bare type name, whatever the letters add up to."""
    html, findings = render(
        "<ddue:para><ddue:codeInline>wing<ddue:subscript>Type</ddue:subscript></ddue:codeInline></ddue:para>",
        type_names=CATALOGUE,
    )
    assert html == "<p><code>wing<sub>Type</sub></code></p>"
    assert findings == []


def test_an_explicit_link_keeps_the_words_the_author_wrote():
    html, findings = render(
        '<ddue:para>See the <ddue:link xlink:href="wingSectionType">sections of a wing'
        "</ddue:link>.</ddue:para>",
        type_names=CATALOGUE,
    )
    assert html == (
        '<p>See the <span class="cd-xref" data-type="wingSectionType">'
        "sections of a wing</span>.</p>"
    )
    assert findings == []


def test_an_empty_link_is_labelled_with_its_target():
    html, findings = render(
        '<ddue:para>See <ddue:link xlink:href="wingType"/>.</ddue:para>', type_names=CATALOGUE
    )
    assert html == '<p>See <span class="cd-xref" data-type="wingType">wingType</span>.</p>'
    assert findings == []


def test_a_link_without_a_target_is_an_error_and_keeps_its_text():
    html, findings = render("<ddue:para>See <ddue:link>a wing</ddue:link>.</ddue:para>",
                            type_names=CATALOGUE)
    assert html == "<p>See a wing.</p>"
    assert [(f.severity, f.code) for f in findings] == [("error", "RENDER_LINK_WITHOUT_TARGET")]


def test_a_link_to_an_unknown_type_is_an_error():
    """The one thing an explicit link buys over an attribute nobody reads: a
    typo in the target is reported rather than rendered as ordinary prose."""
    html, findings = render(
        '<ddue:para>See <ddue:link xlink:href="wingTpye">a wing</ddue:link>.</ddue:para>',
        type_names=CATALOGUE,
    )
    assert html == "<p>See a wing.</p>"
    assert [(f.severity, f.code) for f in findings] == [("error", "RENDER_LINK_UNRESOLVED")]


def test_a_link_without_a_catalogue_to_check_against_is_a_warning():
    _, findings = render('<ddue:para><ddue:link xlink:href="wingType">a wing</ddue:link></ddue:para>')
    assert [(f.severity, f.code) for f in findings] == [("warning", "RENDER_LINK_UNRESOLVED")]


def test_a_type_name_inside_a_hand_written_link_is_not_linked_again():
    """Nesting one anchor inside another is invalid markup, and the author has
    already said where these words lead."""
    html, findings = render(
        '<ddue:para><ddue:link xlink:href="wingType">see <ddue:codeInline>wingSectionType'
        "</ddue:codeInline></ddue:link></ddue:para>",
        type_names=CATALOGUE,
    )
    assert html == (
        '<p><span class="cd-xref" data-type="wingType">see '
        "<code>wingSectionType</code></span></p>"
    )
    assert findings == []
