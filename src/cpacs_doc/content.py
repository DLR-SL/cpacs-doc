"""Attributes, enumeration values and child elements of a type.

The catalogue built in `catalogue.py` records what a type *is*; this module
records what it *contains* — the three things a type page has to show that the
build report never needed (F7, F8, F9).

Attributes are collected along the inheritance chain, because that is how an
instance sees them: 1,080 of the 1,101 types extend another type, and 300 of
the 311 attribute declarations sit on an `xsd:extension` rather than directly on
a complexType. Each attribute records where it was declared, so a type page can
tell its own attributes from inherited ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from . import annotations as ann
from .catalogue import inline_type, synthetic_name
from .annotations import XSD, Documentation, local, location_of, q
from .findings import Finding

COMPOSITORS = ("sequence", "choice", "all")


@dataclass
class AttributeInfo:
    name: str
    type_name: str | None
    use: str              # "required" | "optional"
    default: str | None
    fixed: str | None
    declared_in: str      # type name the declaration was found on
    inherited: bool
    doc: Documentation
    line: int | None


@dataclass
class EnumerationValue:
    value: str
    doc: Documentation
    line: int | None


@dataclass
class Facet:
    """One constraining facet: what a value must satisfy to be allowed.

    Kept apart from the enumeration, which answers a different question — the
    enumeration lists the values, a facet narrows the space they come from —
    and which carries documentation of its own where a facet never does.
    """

    name: str
    value: str
    line: int | None


@dataclass
class ChildInfo:
    name: str
    type_name: str | None
    min_occurs: int
    max_occurs: int | None
    doc: Documentation
    line: int | None
    # The declaration itself, for the tree to expand from. Not serialised.
    node: etree._Element = field(repr=False, default=None)


@dataclass
class ChildGroup:
    """A compositor and what it contains.

    Children form a tree, not a list: 84 `choice` groups in the schema decide
    between alternatives, 48 of them between groups of elements rather than
    single ones, and 14 are optional as a whole. Flattening that into one
    attribute per child cannot express which children belong to the same
    decision, and ten types contain more than one.
    """

    compositor: str
    min_occurs: int
    max_occurs: int | None
    members: list["ChildInfo | ChildGroup"] = field(default_factory=list)
    line: int | None = None


@dataclass
class TypeContent:
    attributes: list[AttributeInfo] = field(default_factory=list)
    enumeration: list[EnumerationValue] = field(default_factory=list)
    facets: list[Facet] = field(default_factory=list)
    children: list[ChildInfo] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.attributes or self.enumeration or self.facets or self.children)


def inline_reference(node, catalogue) -> str | None:
    """Catalogue name of a type the declaration itself declares.

    An element or an attribute may declare its type on the spot instead of
    naming one. The catalogue gives such a type a synthetic name and a page of
    its own (0003); without naming it here the declaration would point at
    nothing, and what the type says — 217 of the schema's 265 enumeration
    values sit in exactly these — could not be reached from the page that needs
    it.

    Only a name the catalogue actually holds is returned. A synthetic name can
    collide, and the catalogue reports that rather than overwriting; pointing
    at the loser of a collision would be worse than pointing at nothing.
    """
    if inline_type(node) is None:
        return None
    name = synthetic_name(node)
    return name if name in catalogue.types else None


def content_groups(node, catalogue, source: str, findings: list["Finding"]) -> list["ChildGroup"]:
    """Compositor groups of a type, base content first.

    Shared with `tree.py`: two traversals of the same schema structure would
    drift apart, and the tree already once ordered inherited content the wrong
    way round.
    """
    holder_content = _TypeContent_for_findings(findings)
    groups: list[ChildGroup] = []
    for holder, _, _ in reversed(list(_holders(node, catalogue))):
        for compositor_name in COMPOSITORS:
            compositor = holder.find(q(XSD, compositor_name))
            if compositor is None:
                continue
            groups.append(
                _read_group(compositor, compositor_name, _Anonymous(node), source,
                            holder_content, catalogue)
            )
    return groups


class _Anonymous:
    """Minimal stand-in where only a name is needed for a finding message."""

    def __init__(self, node):
        self.name = node.get("name") or "<anonymous>"


class _TypeContent_for_findings:
    """Collects findings without building a full TypeContent."""

    def __init__(self, findings):
        self.findings = findings


def read(info, catalogue, source: str) -> TypeContent:
    """Collect attributes, enumeration values and children of one type."""
    content = TypeContent()
    if info.node is None:
        return content

    _attributes(info, catalogue, source, content)
    _enumeration(info, source, content)
    _facets(info, source, content)
    content.children = content_groups(info.node, catalogue, source, content.findings)
    return content


def _holders(node, catalogue, seen=None):
    """The type itself plus its base types, nearest first.

    Yields (holder, owning type name, inherited). The holder is the element that
    directly carries declarations: an `xsd:extension` where the type derives,
    the complexType itself where it does not.

    Nearest-first is the order attributes need, because a derived type may
    narrow an inherited attribute and the nearest declaration is the one an
    instance sees. Child elements need the opposite order — see `_children`.
    """
    seen = seen if seen is not None else set()
    if id(node) in seen:
        return
    seen.add(id(node))

    for container in ("complexContent", "simpleContent"):
        wrapper = node.find(q(XSD, container))
        if wrapper is None:
            continue
        for kind in ("extension", "restriction"):
            derived = wrapper.find(q(XSD, kind))
            if derived is None:
                continue
            yield derived, node.get("name"), False
            base = catalogue.get(derived.get("base") or "")
            if base is not None and base.node is not None:
                for holder, owner, _ in _holders(base.node, catalogue, seen):
                    yield holder, owner or base.name, True
            return

    yield node, node.get("name"), False


def _attributes(info, catalogue, source, content) -> None:
    seen: dict[str, AttributeInfo] = {}
    for holder, owner, inherited in _holders(info.node, catalogue):
        for node in holder.findall(q(XSD, "attribute")):
            name = node.get("name")
            if not name:
                # @ref does not occur in the schema; if it appears, resolving it
                # needs a global attribute table this module does not build.
                content.findings.append(
                    Finding(
                        "error",
                        "ATTRIBUTE_WITHOUT_NAME",
                        f"{info.name}: xsd:attribute without @name",
                        location_of(node, source),
                    )
                )
                continue
            if name in seen:
                # A derived type may restrict an inherited attribute. The
                # nearest declaration wins, which is the one already recorded.
                continue

            doc, problems = ann.read(node.find(q(XSD, "annotation")), source, f"attribute {info.name}/@{name}")
            content.findings.extend(problems)

            use = node.get("use")
            if use is None:
                use = "optional"
            elif use not in ("required", "optional", "prohibited"):
                content.findings.append(
                    Finding(
                        "warning",
                        "ATTRIBUTE_USE_UNKNOWN",
                        f"{info.name}/@{name}: unknown use {use!r}",
                        location_of(node, source),
                    )
                )

            seen[name] = AttributeInfo(
                name=name,
                type_name=(node.get("type") or inline_reference(node, catalogue)
                           or _inline_base(node)),
                use=use,
                default=node.get("default"),
                fixed=node.get("fixed"),
                declared_in=owner or info.name,
                inherited=inherited,
                doc=doc,
                line=getattr(node, "sourceline", None),
            )

    content.attributes = sorted(seen.values(), key=lambda a: a.name)


def _inline_base(node) -> str | None:
    """Base of an attribute's inline simpleType, where it has one."""
    simple = node.find(q(XSD, "simpleType"))
    if simple is None:
        return None
    restriction = simple.find(q(XSD, "restriction"))
    return restriction.get("base") if restriction is not None else None


def _enumeration(info, source, content) -> None:
    """Enumeration values of this type only.

    Searched along explicit paths rather than with `iter()`: descending freely
    would also collect the values of child elements that carry an inline
    simpleType, which belong to those children and are catalogued separately.
    """
    for restriction in _restrictions(info.node):
        for node in restriction.findall(q(XSD, "enumeration")):
            value = node.get("value")
            if value is None:
                content.findings.append(
                    Finding(
                        "error",
                        "ENUMERATION_WITHOUT_VALUE",
                        f"{info.name}: xsd:enumeration without @value",
                        location_of(node, source),
                    )
                )
                continue
            doc, problems = ann.read(
                node.find(q(XSD, "annotation")), source, f"enumeration {info.name}/{value}"
            )
            content.findings.extend(problems)
            content.enumeration.append(
                EnumerationValue(value=value, doc=doc, line=getattr(node, "sourceline", None))
            )


# Every constraining facet XSD defines, less `enumeration`, which is read on
# its own. In document order, because `pattern` may appear more than once and
# the alternatives then read as they were written.
FACETS = (
    "length", "minLength", "maxLength", "pattern", "whiteSpace",
    "maxInclusive", "maxExclusive", "minInclusive", "minExclusive",
    "totalDigits", "fractionDigits",
)


def _facets(info, source, content) -> None:
    """What narrows this type's value space, beyond the values it lists.

    Along the same explicit paths as the enumeration and for the same reason: a
    free descent would take the constraints of a child that declares its own
    type and attribute them to the parent.
    """
    for restriction in _restrictions(info.node):
        for node in restriction:
            if not isinstance(node.tag, str):
                continue
            name = local(node.tag)
            if name not in FACETS:
                continue
            value = node.get("value")
            if value is None:
                content.findings.append(
                    Finding(
                        "error",
                        "FACET_WITHOUT_VALUE",
                        f"{info.name}: xsd:{name} without @value",
                        location_of(node, source),
                    )
                )
                continue
            content.facets.append(
                Facet(name=name, value=value, line=getattr(node, "sourceline", None))
            )


def _restrictions(node):
    """Restrictions that constrain this type's own value space."""
    direct = node.find(q(XSD, "restriction"))
    if direct is not None:
        yield direct
    for container in ("simpleContent", "complexContent"):
        wrapper = node.find(q(XSD, container))
        if wrapper is None:
            continue
        restriction = wrapper.find(q(XSD, "restriction"))
        if restriction is not None:
            yield restriction
    # An element declaring an inline simpleType: the values are the element's.
    inline = node.find(q(XSD, "simpleType"))
    if inline is not None:
        restriction = inline.find(q(XSD, "restriction"))
        if restriction is not None:
            yield restriction


def _read_group(node, compositor_name, info, source, content, catalogue) -> ChildGroup:
    group = ChildGroup(
        compositor=compositor_name,
        min_occurs=_occurs(node.get("minOccurs"), 1),
        max_occurs=_occurs(node.get("maxOccurs"), 1),
        line=getattr(node, "sourceline", None),
    )
    for child in node:
        if not isinstance(child.tag, str):
            continue
        name = local(child.tag)
        if name in COMPOSITORS:
            group.members.append(_read_group(child, name, info, source, content, catalogue))
        elif name == "element":
            member = _read_child(child, info, source, content, catalogue)
            if member is not None:
                group.members.append(member)
    return group


def _read_child(node, info, source, content, catalogue) -> ChildInfo | None:
    declared = node.get("name") or node.get("ref")
    if not declared:
        content.findings.append(
            Finding(
                "error",
                "CHILD_WITHOUT_NAME",
                f"{info.name}: xsd:element without @name or @ref",
                location_of(node, source),
            )
        )
        return None
    doc, problems = ann.read(
        node.find(q(XSD, "annotation")), source, f"element {info.name}/{declared}"
    )
    content.findings.extend(problems)
    return ChildInfo(
        name=declared,
        type_name=node.get("type") or inline_reference(node, catalogue),
        min_occurs=_occurs(node.get("minOccurs"), 1),
        max_occurs=_occurs(node.get("maxOccurs"), 1),
        doc=doc,
        line=getattr(node, "sourceline", None),
        node=node,
    )


def _occurs(value, default):
    if value is None:
        return default
    if value == "unbounded":
        return None
    try:
        return int(value)
    except ValueError:
        return default
