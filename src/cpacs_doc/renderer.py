"""Rendering `ddue` markup to HTML.

One renderer, in Python, used twice: the generator writes the static type pages
with it, and the same HTML is carried in the model for the viewer to insert into
its detail panel. A second implementation in JavaScript would be a second thing
to keep in step, and rendering differences between the two views would be
invisible until someone compared them side by side.

The vocabulary is closed (see `annotations.KNOWN_DDUE`). An element outside it
is reported and its text content passed through, so no documentation is lost
while the gap is being closed.

No header row is inferred for tables. Two of the thirteen tables in the schema
mark their first row with `legacyBold`; the rest do not, and promoting the first
row to `<th>` would be a guess about the other eleven.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from textwrap import dedent

from lxml import etree

from .annotations import DDUE, KNOWN_DDUE, XLINK, XSD, local, location_of, q
from .findings import Finding

CLASS_PREFIX = "cd-"

# Elements whose text content is significant as written. Everywhere else runs of
# whitespace collapse, because the schema indents its documentation bodies by
# up to thirty columns.
PREFORMATTED = frozenset({"code"})

INLINE_TAGS = {
    "legacyBold": "strong",
    "legacyItalic": "em",
    "emphasis": "em",
    "superscript": "sup",
    "subscript": "sub",
}

LIST_CLASSES = {"bullet": "ul", "ordered": "ol"}

# `ddue:alert` sets a note apart from the normative text of the schema. CPACS is
# a tool-independent standard, but most readers process it with TiGL; a `tigl`
# alert says how TiGL treats the data where that differs from or goes beyond
# the text around it. The label names the kind, so that the distinction does
# not rest on the colour of the rule alone.
ALERT_LABELS = {"note": "Note", "tigl": "TiGL"}


@dataclass
class RenderContext:
    # image id -> {"file", "alt"}. None means no catalogue was supplied, which
    # is a deliberate choice by the caller rather than a broken reference.
    media: dict[str, dict] | None = None
    # Every type name the schema declares, for the cross references below. None
    # means no catalogue was supplied, as with `media`: nothing is linked and
    # nothing is reported.
    type_names: frozenset[str] | None = None
    # Placeholder for the path back to the output root. The renderer cannot know
    # how deep the page consuming this fragment sits, and the same fragment is
    # used by pages at different depths and by the viewer. Whoever writes the
    # page substitutes it — see generator.ROOT_TOKEN.
    asset_prefix: str = "%ROOT%"
    source: str = ""
    owner: str = ""
    findings: list[Finding] = field(default_factory=list)

    def report(self, severity, code, message, node=None):
        self.findings.append(
            Finding(
                severity,
                code,
                f"{self.owner}: {message}" if self.owner else message,
                location_of(node, self.source) if node is not None else self.source,
            )
        )


def render(node: etree._Element | None, context: RenderContext) -> str:
    """Render one `ddue` subtree. Returns an empty string for `None`."""
    if node is None:
        return ""
    # Stripped: the schema indents its documentation bodies, so the first and
    # last text nodes are almost always whitespace.
    return "".join(_children(node, context)).strip()


def _children(node, context) -> list[str]:
    parts = [_text(node.text, node, context)]
    for child in node:
        if isinstance(child.tag, str):
            parts.append(_element(child, context))
        parts.append(_text(child.tail, node, context))
    return [p for p in parts if p]


def _text(value, parent, context) -> str:
    if not value:
        return ""
    if local(parent.tag) in PREFORMATTED:
        return escape(value)
    collapsed = re.sub(r"\s+", " ", value)
    return escape(collapsed)


def _element(node, context) -> str:
    name = local(node.tag)
    if node.tag == q(XSD, "xmlEntityReference"):
        return _entity_reference(node, context)
    if not node.tag.startswith("{" + DDUE + "}"):
        context.report("error", "RENDER_FOREIGN_ELEMENT", f"non-ddue element {name!r} in documentation", node)
        return escape(" ".join("".join(node.itertext()).split()))
    if name not in KNOWN_DDUE:
        context.report("error", "RENDER_UNKNOWN_ELEMENT", f"ddue:{name} has no rendering", node)
        return escape(" ".join("".join(node.itertext()).split()))

    handler = _HANDLERS.get(name)
    if handler is None:
        context.report("error", "RENDER_NOT_IMPLEMENTED", f"ddue:{name} is known but unhandled", node)
        return escape(" ".join("".join(node.itertext()).split()))
    return handler(node, context)


def _wrap(tag, node, context, css=None, attributes=""):
    inner = "".join(_children(node, context))
    classes = f' class="{CLASS_PREFIX}{css}"' if css else ""
    return f"<{tag}{classes}{attributes}>{inner}</{tag}>"


def _block(tag, css=None):
    return lambda node, context: _wrap(tag, node, context, css)


def _inline(name):
    return lambda node, context: _wrap(INLINE_TAGS[name], node, context)


def _list(node, context):
    css_class = node.get("class")
    tag = LIST_CLASSES.get(css_class)
    if tag is None:
        context.report(
            "warning",
            "RENDER_LIST_CLASS_UNKNOWN",
            f"ddue:list with class {css_class!r}; rendered unordered",
            node,
        )
        tag = "ul"
    return _wrap(tag, node, context, css="list")


def _alert(node, context):
    kind = node.get("class")
    if kind not in ALERT_LABELS:
        context.report(
            "warning",
            "RENDER_ALERT_CLASS_UNKNOWN",
            f"ddue:alert with class {kind!r}; rendered as note",
            node,
        )
        kind = "note"
    inner = "".join(_children(node, context))
    return (
        f'<aside class="{CLASS_PREFIX}alert {CLASS_PREFIX}alert-{kind}" role="note">'
        f'<p class="{CLASS_PREFIX}alert-label">{ALERT_LABELS[kind]}</p>{inner.strip()}</aside>'
    )


# All 50 code blocks in CPACS 3.5.1 are `language="XML"`, and every one of them
# is an excerpt of an instance document. What a reader has to pick out of them
# is which words are element names, which are attributes and which are values —
# the same distinction the rest of the page draws between schema vocabulary and
# prose about it. Marked here, in the one renderer, because the viewer inserts
# these fragments as they are.
#
# A tokeniser, not a parser: 13 of the 50 carry `...` where the document goes
# on, and all but 3 begin in the middle of a document rather than at its root,
# so a parser would reject them. Whatever is not recognised stays text,
# escaped, rather than being guessed at.
_XML_TOKEN = re.compile(
    r"(?P<comment><!--.*?(?:-->|\Z))"
    r"|(?P<meta><[?!][^>]*(?:>|\Z))"
    r"""|(?P<tag></?[A-Za-z_][\w.:-]*(?:"[^"]*"|'[^']*'|[^<>"'])*>)""",
    re.DOTALL,
)
_XML_ATTRIBUTE = re.compile(r"""([A-Za-z_][\w.:-]*)(\s*=\s*)("[^"]*"|'[^']*')""")
_XML_NAME = re.compile(r"</?[A-Za-z_][\w.:-]*")


def _mark(kind: str, text: str) -> str:
    return f'<span class="{CLASS_PREFIX}{kind}">{escape(text)}</span>'


def _highlight_xml(text: str) -> str:
    """XML source with its parts marked. What is not recognised stays text."""
    out = []
    position = 0
    for match in _XML_TOKEN.finditer(text):
        out.append(escape(text[position:match.start()]))
        if match.lastgroup == "tag":
            out.append(_highlight_tag(match.group()))
        else:
            out.append(_mark(match.lastgroup, match.group()))
        position = match.end()
    out.append(escape(text[position:]))
    return "".join(out)


def _highlight_tag(tag: str) -> str:
    name = _XML_NAME.match(tag).group()
    bracket = 2 if name.startswith("</") else 1
    parts = [_mark("punct", name[:bracket]), _mark("tag", name[bracket:])]
    rest = tag[len(name):]
    position = 0
    for attribute in _XML_ATTRIBUTE.finditer(rest):
        parts.append(escape(rest[position:attribute.start()]))
        parts.append(_mark("attr", attribute.group(1)))
        parts.append(_mark("punct", attribute.group(2)))
        parts.append(_mark("value", attribute.group(3)))
        position = attribute.end()
    if rest[position:]:
        parts.append(_mark("punct", rest[position:]))
    return "".join(parts)


def _code(node, context):
    language = node.get("language")
    title = node.get("title")
    # Highlighted only where the block is text through and through. A code
    # block holding markup of its own keeps the path that renders that markup;
    # none in this schema does (measured: 0 of 50).
    if language == "XML" and len(node) == 0:
        body = _highlight_xml(dedent(node.text or "").strip("\n"))
    else:
        body = dedent("".join(_children(node, context))).strip("\n")
    attributes = f' data-language="{escape(language)}"' if language else ""
    block = f'<pre class="{CLASS_PREFIX}code"{attributes}><code>{body}</code></pre>'
    if title:
        return f'<figure class="{CLASS_PREFIX}code-figure">{block}<figcaption>{escape(title)}</figcaption></figure>'
    return block


def _title(node, context):
    # Inside a table the title is its caption; elsewhere it heads a section.
    parent = node.getparent()
    tag = "caption" if parent is not None and local(parent.tag) == "table" else "h3"
    return _wrap(tag, node, context)


def _table(node, context):
    rows = "".join(_children(node, context))
    return f'<table class="{CLASS_PREFIX}table">{rows}</table>'


def _image(node, context):
    image_id = node.get(q(XLINK, "href"))
    if not image_id:
        context.report("error", "RENDER_IMAGE_WITHOUT_HREF", "ddue:image without xlink:href", node)
        return ""
    entry = (context.media or {}).get(image_id)
    if entry is None:
        severity = "warning" if context.media is None else "error"
        context.report(severity, "RENDER_IMAGE_UNRESOLVED", f"no media entry for {image_id!r}", node)
        return f'<span class="{CLASS_PREFIX}missing-image" data-image-id="{escape(image_id)}"></span>'

    source = f"{context.asset_prefix}/media/{entry['file']}"
    width = node.get("width")
    size = f' width="{escape(width)}"' if width else ""
    return (
        f'<img class="{CLASS_PREFIX}image" src="{escape(source)}" '
        f'alt="{escape(entry["alt"])}"{size}>'
    )


def _entity_reference(node, context):
    """Sandcastle's cross-reference into another type page.

    The target is written as `Empty#T/<typeName>`; only the type name after the
    last slash carries meaning here. Resolution against the catalogue happens in
    the generator, which knows the URL layout — this stage marks the reference
    and leaves the target in a data attribute. It names a type, so it is
    marked the way rule A marks one.
    """
    raw = " ".join("".join(node.itertext()).split())
    target = raw.rsplit("/", 1)[-1] if raw else ""
    if not target:
        context.report("warning", "RENDER_XREF_EMPTY", "xsd:xmlEntityReference without a target", node)
        return ""
    return _xref("code", target, escape(target))


def _xref(tag: str, target: str, inner: str) -> str:
    """The marker a cross reference leaves behind.

    The renderer does not resolve it: the same fragment is read by pages at
    three different depths and by the viewer, and none of them may have the URL
    layout baked in. `code` carries a type name, which is schema vocabulary and
    is set as such; `span` carries the words an author chose instead.
    """
    return f'<{tag} class="{CLASS_PREFIX}xref" data-type="{escape(target)}">{inner}</{tag}>'


def _inside_link(node) -> bool:
    """Whether this node sits inside a `ddue:link`.

    A reference inside a reference is not a second reference: the author has
    already said where these words lead, and marking a type name within the
    label would nest one anchor inside another.
    """
    parent = node.getparent()
    while parent is not None:
        if parent.tag == q(DDUE, "link"):
            return True
        parent = parent.getparent()
    return False


def _code_inline(node, context):
    """`codeInline` naming a type is a reference to it (rule A).

    The guidelines have element and type names written as `codeInline`, so the
    text is already there; what it lacks is the link. 243 of the 1,103
    occurrences in CPACS 3.5.1 are exactly a global type name, none of them
    names the type it stands in, and nothing else in the schema is spelled that
    way — so the name alone decides, with no annotation to keep up to date.

    Element names are deliberately not resolved here. 186 element names are
    declared with more than one type, so the name on its own does not say which
    page it means; an author who wants that link writes `ddue:link`.
    """
    inner = "".join(_children(node, context))
    names = context.type_names
    if names is not None and len(node) == 0 and not _inside_link(node):
        text = " ".join((node.text or "").split())
        if text in names:
            return _xref("code", text, escape(text))
    return f"<code>{inner}</code>"


def _link(node, context):
    """`ddue:link` — the reference an author sets by hand.

    What rule A cannot do: name a type in words of the author's own ("the rotor
    blades"), or send a reader from an element name to the type behind it,
    which the bare name does not identify. The target is a type name either
    way, in `xlink:href`, as `ddue:image` names its media entry. An empty
    element takes its target as its label.

    Unlike an attribute on `codeInline`, a wrong target here is reported: the
    vocabulary is closed and this element exists to be checked.
    """
    target = (node.get(q(XLINK, "href")) or "").strip()
    inner = "".join(_children(node, context)).strip()
    if not target:
        context.report("error", "RENDER_LINK_WITHOUT_TARGET", "ddue:link without xlink:href", node)
        return inner
    label = inner or escape(target)
    if context.type_names is None or target not in context.type_names:
        severity = "warning" if context.type_names is None else "error"
        context.report(severity, "RENDER_LINK_UNRESOLVED", f"no type named {target!r}", node)
        return label
    return _xref("span", target, label)


def _external_link(node, context):
    uri = node.find(q(DDUE, "linkUri"))
    text = node.find(q(DDUE, "linkText"))
    if uri is None or not (uri.text or "").strip():
        context.report("error", "RENDER_LINK_WITHOUT_URI", "ddue:externalLink without linkUri", node)
        return escape(" ".join("".join(node.itertext()).split()))
    target = uri.text.strip()
    label = " ".join("".join(text.itertext()).split()) if text is not None else target
    return f'<a class="{CLASS_PREFIX}link" href="{escape(target)}" rel="noopener">{escape(label)}</a>'


_HANDLERS = {
    "summary": _block("div", "summary"),
    "remarks": _block("div", "remarks"),
    "content": _block("div", "content"),
    "section": _block("section", "section"),
    "para": _block("p"),
    "list": _list,
    "listItem": _block("li"),
    "alert": _alert,
    "definitionTable": _block("dl", "definitions"),
    "definedTerm": _block("dt"),
    "definition": _block("dd"),
    "table": _table,
    "row": _block("tr"),
    "entry": _block("td"),
    "title": _title,
    "code": _code,
    "mediaLink": _block("figure", "figure"),
    "image": _image,
    "codeInline": _code_inline,
    "link": _link,
    "externalLink": _external_link,
    # linkUri and linkText are consumed by their externalLink parent.
    "linkUri": lambda node, context: "",
    "linkText": lambda node, context: "",
    **{name: _inline(name) for name in INLINE_TAGS},
}
