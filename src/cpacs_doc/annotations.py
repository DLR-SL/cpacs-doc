"""Reading documentation off an `xsd:annotation`.

CPACS carries documentation in two disjoint channels:

* `xsd:appinfo/sd:schemaDoc` — the type documentation, structured `ddue` markup
  under `summary` and `remarks`. 1,090 occurrences.
* `xsd:documentation` — the element one-liner. 2,091 occurrences, of which 1,978
  sit on `xsd:element`. Only four annotations carry both.

The two are treated differently on purpose. Type documentation keeps its markup,
because it has to be rendered. Element documentation is flattened to text; the
single occurrence carrying inline markup is reported rather than silently
stripped.

The `ddue` vocabulary is treated as closed. Anything outside the measured set is
a finding, never a guess about how it should render.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from .findings import Finding

XSD = "http://www.w3.org/2001/XMLSchema"
DDUE = "http://ddue.schemas.microsoft.com/authoring/2003/5"
SD = "http://schemas.xsddoc.codeplex.com/schemaDoc/2009/3"
XLINK = "http://www.w3.org/1999/xlink"

# Measured against DLR-SL/CPACS develop, commit 4beeef8. An element outside this
# set means the vocabulary has grown and the renderer needs a decision, so it is
# reported instead of being passed through untranslated.
KNOWN_DDUE = frozenset(
    {
        "code", "codeInline", "content", "definedTerm", "definition",
        "definitionTable", "emphasis", "entry", "externalLink", "image",
        "legacyBold", "legacyItalic", "linkText", "linkUri", "list", "listItem",
        "math", "mediaLink", "para", "remarks", "row", "section", "summary",
        "superscript", "table", "title",
    }
)

# Direct children of sd:schemaDoc that the rest of the schema uses.
EXPECTED_SCHEMADOC_CHILDREN = frozenset({"summary", "remarks"})


def q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def local(tag) -> str:
    return tag.split("}")[-1] if isinstance(tag, str) else str(tag)


@dataclass
class Documentation:
    """What one annotation yields.

    `summary` and `remarks` are the raw `ddue` subtrees, kept as elements so the
    renderer in a later phase receives the markup unaltered. `text` is the
    flattened element one-liner.
    """

    summary: etree._Element | None = None
    remarks: etree._Element | None = None
    text: str = ""
    image_ids: set[str] = field(default_factory=set)
    ddue_elements: set[str] = field(default_factory=set)

    @property
    def is_empty(self) -> bool:
        return self.summary is None and self.remarks is None and not self.text


def location_of(node: etree._Element, source: str) -> str:
    line = getattr(node, "sourceline", None)
    return f"{source}:{line}" if line else source


def read(annotation: etree._Element | None, source: str, owner: str) -> tuple[Documentation, list[Finding]]:
    """Extract documentation from one `xsd:annotation`.

    `owner` is a human-readable identification of the construct the annotation
    belongs to, used verbatim in findings.
    """
    doc = Documentation()
    problems: list[Finding] = []
    if annotation is None:
        return doc, problems

    for appinfo in annotation.findall(q(XSD, "appinfo")):
        for schema_doc in appinfo.findall(q(SD, "schemaDoc")):
            _read_schema_doc(schema_doc, doc, problems, source, owner)

    documentation = annotation.find(q(XSD, "documentation"))
    if documentation is not None:
        _read_element_doc(documentation, doc, problems, source, owner)

    return doc, problems


def _read_schema_doc(schema_doc, doc, problems, source, owner) -> None:
    where = location_of(schema_doc, source)
    children = [c for c in schema_doc if isinstance(c.tag, str)]
    names = [local(c.tag) for c in children]

    unexpected = [n for n in names if n not in EXPECTED_SCHEMADOC_CHILDREN]
    if unexpected:
        problems.append(
            Finding(
                "warning",
                "SCHEMADOC_UNEXPECTED_CHILD",
                f"{owner}: sd:schemaDoc contains {unexpected} where only "
                f"{sorted(EXPECTED_SCHEMADOC_CHILDREN)} are used elsewhere",
                where,
            )
        )

    for child in children:
        name = local(child.tag)
        if name == "summary":
            if doc.summary is not None:
                problems.append(
                    Finding("warning", "SCHEMADOC_DUPLICATE", f"{owner}: more than one ddue:summary", where)
                )
            doc.summary = child
        elif name == "remarks":
            if doc.remarks is not None:
                problems.append(
                    Finding("warning", "SCHEMADOC_DUPLICATE", f"{owner}: more than one ddue:remarks", where)
                )
            doc.remarks = child

    # A remarks nested below content is unreachable for a consumer reading the
    # expected children, so it is reported rather than recovered by searching.
    for remarks in schema_doc.iter(q(DDUE, "remarks")):
        if remarks.getparent() is not schema_doc:
            problems.append(
                Finding(
                    "warning",
                    "SCHEMADOC_NESTED_REMARKS",
                    f"{owner}: ddue:remarks nested inside ddue:{local(remarks.getparent().tag)}, "
                    f"not a direct child of sd:schemaDoc",
                    location_of(remarks, source),
                )
            )

    if doc.summary is None:
        problems.append(
            Finding("warning", "SCHEMADOC_NO_SUMMARY", f"{owner}: sd:schemaDoc without ddue:summary", where)
        )

    _survey_markup(schema_doc, doc, problems, source, owner)


def _read_element_doc(documentation, doc, problems, source, owner) -> None:
    where = location_of(documentation, source)
    markup = [local(c.tag) for c in documentation if isinstance(c.tag, str)]
    if markup:
        problems.append(
            Finding(
                "info",
                "ELEMENTDOC_MARKUP_FLATTENED",
                f"{owner}: xsd:documentation contains inline markup {markup}; "
                f"kept as plain text",
                where,
            )
        )
    doc.text = " ".join("".join(documentation.itertext()).split())


def _survey_markup(root, doc, problems, source, owner) -> None:
    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith("{" + DDUE + "}"):
            continue
        name = local(node.tag)
        doc.ddue_elements.add(name)
        if name not in KNOWN_DDUE:
            problems.append(
                Finding(
                    "error",
                    "DDUE_UNKNOWN_ELEMENT",
                    f"{owner}: ddue:{name} is outside the known vocabulary",
                    location_of(node, source),
                )
            )
        if name == "image":
            href = node.get(q(XLINK, "href"))
            if href:
                doc.image_ids.add(href)
            else:
                problems.append(
                    Finding(
                        "error",
                        "IMAGE_WITHOUT_HREF",
                        f"{owner}: ddue:image without xlink:href",
                        location_of(node, source),
                    )
                )
