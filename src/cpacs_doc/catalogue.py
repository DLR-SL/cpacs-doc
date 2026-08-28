"""The type catalogue.

CPACS puts documentation on types while the navigable tree sits on elements, so
the catalogue is the anchor the tree later refers into. It holds every named
global type plus the eleven documented constructs that are not global
complexTypes — five simpleTypes and six local elements. A purely type-oriented
extractor loses those.

Anonymous inline types are catalogued as well, keyed by the path of their owning
element, because a documented element with an inline type would otherwise have
nowhere to attach.

Single-file assumption: the schema uses no `include`, `import`, `redefine` or
`override` (measured: zero of each). If one appears, it is reported — resolving
it would need a different loading strategy than parsing one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from . import annotations as ann
from .annotations import DDUE, SD, XSD, Documentation, local, location_of, q
from .findings import Finding

COMPOSITORS = ("sequence", "choice", "all")
MODULARISATION = ("include", "import", "redefine", "override")


@dataclass
class TypeInfo:
    name: str          # global name, or a synthetic name for anonymous types
    kind: str          # "complexType" | "simpleType" | "element"
    anonymous: bool
    base: str | None   # base type of an extension or restriction
    derivation: str | None  # "extension" | "restriction" | None
    compositor: str | None  # outermost compositor of a complexType
    doc: Documentation
    line: int | None
    simple_content: bool = False  # an instance writes a value into the element
    node: etree._Element = field(repr=False, default=None)

    @property
    def documented(self) -> bool:
        return not self.doc.is_empty


@dataclass
class Catalogue:
    types: dict[str, TypeInfo] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def get(self, name: str) -> TypeInfo | None:
        return self.types.get(name)

    @property
    def undocumented(self) -> list[TypeInfo]:
        return [t for t in self.types.values() if not t.documented]


def build(root: etree._Element, source: str) -> Catalogue:
    catalogue = Catalogue()

    for kind in MODULARISATION:
        for node in root.iter(q(XSD, kind)):
            catalogue.findings.append(
                Finding(
                    "error",
                    "SCHEMA_NOT_SINGLE_FILE",
                    f"xsd:{kind} found; the extractor parses a single schema file",
                    location_of(node, source),
                )
            )

    for kind in ("complexType", "simpleType"):
        for node in root.findall(q(XSD, kind)):
            _add_named(node, kind, catalogue, source)

    _add_documented_locals(root, catalogue, source)
    _add_anonymous(root, catalogue, source)

    return catalogue


def _add_named(node, kind, catalogue, source) -> None:
    name = node.get("name")
    if not name:
        return
    if name in catalogue.types:
        catalogue.findings.append(
            Finding(
                "error",
                "TYPE_DUPLICATE_NAME",
                f"{kind} {name!r} declared more than once",
                location_of(node, source),
            )
        )
        return
    catalogue.types[name] = _read(node, kind, name, False, catalogue, source)


def _add_documented_locals(root, catalogue, source) -> None:
    """Local elements carrying sd:schemaDoc.

    Documentation on a local element is the exception, not the rule, but it is
    real content and must not be dropped just because the element is not a
    global type.
    """
    for schema_doc in root.iter(q(SD, "schemaDoc")):
        owner = _owning_construct(schema_doc)
        if owner is None or local(owner.tag) != "element":
            continue
        name = synthetic_name(owner)
        if name in catalogue.types:
            continue
        info = _read(owner, "element", name, True, catalogue, source)
        # An element with an inline type is one unit: the element carries the
        # documentation, the anonymous type below it carries the structure.
        inline = inline_type(owner)
        if inline is not None:
            info.base, info.derivation = _derivation(inline)
            info.compositor = _compositor(inline)
            info.simple_content = holds_a_value(inline)
        catalogue.types[name] = info


def _add_anonymous(root, catalogue, source) -> None:
    for kind in ("complexType", "simpleType"):
        for node in root.iter(q(XSD, kind)):
            if node.get("name"):
                continue
            owner = node.getparent()
            name = synthetic_name(owner)
            if name in catalogue.types and inline_type(owner) is node:
                continue  # already folded into the documented element above
            if name in catalogue.types:
                catalogue.findings.append(
                    Finding(
                        "warning",
                        "TYPE_SYNTHETIC_NAME_COLLISION",
                        f"synthetic name {name!r} is not unique",
                        location_of(node, source),
                    )
                )
                continue
            catalogue.types[name] = _read(node, kind, name, True, catalogue, source)


def _read(node, kind, name, anonymous, catalogue, source) -> TypeInfo:
    annotation = node.find(q(XSD, "annotation"))
    owner_label = f"{kind} {name}"
    doc, problems = ann.read(annotation, source, owner_label)
    catalogue.findings.extend(problems)

    base, derivation = _derivation(node)
    return TypeInfo(
        name=name,
        kind=kind,
        anonymous=anonymous,
        base=base,
        derivation=derivation,
        compositor=_compositor(node),
        simple_content=holds_a_value(node),
        doc=doc,
        line=getattr(node, "sourceline", None),
        node=node,
    )


def holds_a_value(node) -> bool:
    """Whether an instance writes a value into the element itself.

    A simple type does by definition. A complexType does when its content is
    simple — 22 of them here, and they are the base types of every measured
    quantity in the schema.
    """
    if local(node.tag) == "simpleType":
        return True
    return node.find(q(XSD, "simpleContent")) is not None


def _derivation(node) -> tuple[str | None, str | None]:
    for container in ("complexContent", "simpleContent"):
        holder = node.find(q(XSD, container))
        if holder is None:
            continue
        for kind in ("extension", "restriction"):
            derived = holder.find(q(XSD, kind))
            if derived is not None:
                return derived.get("base"), kind
    restriction = node.find(q(XSD, "restriction"))
    if restriction is not None:
        return restriction.get("base"), "restriction"
    return None, None


def _compositor(node) -> str | None:
    """Outermost compositor, looking through a derivation if there is one."""
    holders = [node]
    for container in ("complexContent", "simpleContent"):
        holder = node.find(q(XSD, container))
        if holder is not None:
            for kind in ("extension", "restriction"):
                derived = holder.find(q(XSD, kind))
                if derived is not None:
                    holders.append(derived)
    for holder in holders:
        for kind in COMPOSITORS:
            if holder.find(q(XSD, kind)) is not None:
                return kind
    return None


def inline_type(owner):
    """The anonymous complexType or simpleType declared inside `owner`, if any."""
    for kind in ("complexType", "simpleType"):
        child = owner.find(q(XSD, kind))
        if child is not None and not child.get("name"):
            return child
    return None


def _owning_construct(node):
    for ancestor in node.iterancestors():
        if isinstance(ancestor.tag, str) and ancestor.tag.startswith("{" + XSD + "}"):
            if local(ancestor.tag) in ("element", "attribute", "complexType", "simpleType"):
                return ancestor
    return None


def synthetic_name(owner) -> str:
    """Stable identifier for a construct that has no global name.

    Built from the chain of named ancestors so it survives reordering of the
    schema file; the line number would not.

    Public because the declarations have to name the same thing: an element or
    attribute that declares its type on the spot refers to it by this name, and
    a name only one side knows is no reference at all.
    """
    parts = []
    for ancestor in reversed(list(owner.iterancestors())):
        if isinstance(ancestor.tag, str) and ancestor.get("name"):
            parts.append(ancestor.get("name"))
    parts.append(owner.get("name") or local(owner.tag))
    return "/".join(parts)
