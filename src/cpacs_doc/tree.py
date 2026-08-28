"""The instance tree.

The navigable tree is the sequence of elements a CPACS instance may contain,
starting at the single global element `cpacs`. Documentation sits on types,
structure sits on elements; this module produces the element side and records,
for every node, which type it points into.

Recursion is cut, not followed. A type that reappears on its own path would
expand without end, so expansion stops there and the node is marked recursive.
The viewer expands such a node on demand; the extractor does not decide how deep
is deep enough.

Attributes are deliberately absent: they belong to the attribute table of a type
(F7), not to the navigable tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from . import annotations as ann
from .annotations import XSD, Documentation, local, location_of, q
from . import content as content_module
from .catalogue import COMPOSITORS, Catalogue
from .findings import Finding

ROOT_ELEMENT = "cpacs"


@dataclass(frozen=True)
class IdentityConstraint:
    """A key, a reference to one, or a uniqueness rule declared on an element.

    Two in CPACS 3.5.1, both on the root: the version a dataset states must be
    one of the versions its own header lists. That is the only rule the schema
    gives beyond its structure, and nothing showed it — a reader had to open
    the XSD to find out that the two ends have to agree.

    They hang off the declaration, not off the type, so they travel with the
    node rather than with the type page.
    """

    kind: str                  # "key" | "keyref" | "unique"
    name: str | None
    refer: str | None          # the key a keyref points at
    selector: str | None       # the elements the rule applies to
    fields: tuple[str, ...]    # what must be unique, or must match


@dataclass
class Node:
    name: str            # element name as it appears in an instance, or the
                         # compositor for a group node
    path: str            # slash-separated instance path, without a leading slash
    type_name: str | None
    depth: int
    min_occurs: int
    max_occurs: int | None   # None means unbounded
    compositor: str | None   # compositor of the parent that holds this element
    doc: Documentation
    default: str | None = None   # value an instance means by leaving it out
    fixed: str | None = None     # value an instance must write if it writes one
    identity: tuple[IdentityConstraint, ...] = ()
    recursive: bool = False  # expansion stopped: the type is already on this path
    children: list["Node"] = field(default_factory=list)
    line: int | None = None
    # Marks a node that is one alternative of a choice. The tree stays flat —
    # indentation there means containment in an instance, and a compositor is
    # not a container — so the constraint is carried by the node it applies to.
    # The combinations themselves are shown on the type page.
    alternative: bool = False

    @property
    def optional(self) -> bool:
        return self.min_occurs == 0

    @property
    def repeatable(self) -> bool:
        return self.max_occurs is None or self.max_occurs > 1


@dataclass
class Tree:
    root: Node | None = None
    findings: list[Finding] = field(default_factory=list)
    nodes: int = 0        # element nodes; comparable across schema versions
    alternatives: int = 0  # nodes bound to a choice
    max_depth: int = 0
    recursion_cuts: int = 0

    @property
    def distinct_paths(self) -> int:
        return len({n.path for n in self.walk()})

    def walk(self):
        stack = [self.root] if self.root else []
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))


def _declaration_doc(element, source, cache) -> Documentation:
    key = getattr(element, "sourceline", None) or id(element)
    if key not in cache:
        annotation = element.find(q(XSD, "annotation"))
        doc, _ = ann.read(annotation, source, f"element line {key}")
        cache[key] = doc
    return cache[key]


def build(root: etree._Element, catalogue: Catalogue, source: str) -> Tree:
    tree = Tree()
    cache: dict = {}

    globals_ = [e for e in root.findall(q(XSD, "element")) if e.get("name") == ROOT_ELEMENT]
    if not globals_:
        tree.findings.append(
            Finding("error", "TREE_NO_ROOT", f"no global element named {ROOT_ELEMENT!r}", source)
        )
        return tree

    tree.root = _expand(globals_[0], "", 0, root, catalogue, tree, source, frozenset(), cache)
    _report_ambiguous_paths(tree, source)
    return tree


def _report_ambiguous_paths(tree, source) -> None:
    """Paths reachable through more than one branch of a choice.

    The path is the URL under E1, so two nodes sharing one path share one
    address. The target type is what the page shows and is usually identical;
    the cardinality at the insertion point is not, and the viewer has to present
    both readings rather than pick one.
    """
    by_path: dict[str, list[Node]] = {}
    for node in tree.walk():
        by_path.setdefault(node.path, []).append(node)

    for path, nodes in sorted(by_path.items()):
        if len(nodes) < 2:
            continue
        types = {n.type_name for n in nodes}
        occurs = {(n.min_occurs, n.max_occurs) for n in nodes}
        if len(types) > 1:
            severity, detail = "error", f"conflicting types {sorted(map(str, types))}"
        elif len(occurs) > 1:
            severity, detail = "warning", f"differing cardinality {sorted(map(str, occurs))}"
        else:
            severity, detail = "info", "identical declarations"
        tree.findings.append(
            Finding(
                severity,
                "TREE_PATH_AMBIGUOUS",
                f"{path}: reachable {len(nodes)} times ({detail})",
                source,
            )
        )


def _expand(element, parent_path, depth, schema, catalogue, tree, source, seen, cache) -> Node:
    name = element.get("name") or element.get("ref") or "?"
    path = f"{parent_path}/{name}" if parent_path else name
    # An element that declares its type on the spot names it here too, or the
    # declaration would point at nothing and everything the type says would be
    # out of reach from the node that has it.
    type_name = element.get("type") or content_module.inline_reference(element, catalogue)

    # Documentation belongs to the declaration, not to the occurrence: a
    # declaration below a widely reused type is expanded hundreds of times.
    # Reading it once also keeps its findings from being reported once per path
    # — structural defects of a declaration are reported by the catalogue.
    doc = _declaration_doc(element, source, cache)

    node = Node(
        name=name,
        path=path,
        type_name=type_name,
        depth=depth,
        min_occurs=_occurs(element.get("minOccurs"), 1),
        max_occurs=_occurs(element.get("maxOccurs"), 1),
        default=element.get("default"),
        fixed=element.get("fixed"),
        identity=_identity_constraints(element),
        compositor=None,
        doc=doc,
        line=getattr(element, "sourceline", None),
    )
    tree.nodes += 1
    tree.max_depth = max(tree.max_depth, depth)

    definition = _definition(element, catalogue)
    if definition is None:
        if type_name and not type_name.startswith("xsd:"):
            tree.findings.append(
                Finding(
                    "error",
                    "TREE_TYPE_UNRESOLVED",
                    f"{path}: type {type_name!r} is not in the catalogue",
                    location_of(element, source),
                )
            )
        return node

    key = type_name or f"#anonymous:{id(definition)}"
    if key in seen:
        node.recursive = True
        tree.recursion_cuts += 1
        return node

    for member, compositor, alternative in _child_members(definition, catalogue, source, tree):
        child = _expand(member.node, path, depth + 1, schema, catalogue, tree, source,
                        seen | {key}, cache)
        child.compositor = compositor
        child.alternative = alternative
        if alternative:
            tree.alternatives += 1
        node.children.append(child)

    return node


def _identity_constraints(element) -> tuple[IdentityConstraint, ...]:
    """Read in document order: a keyref may stand before the key it refers to,
    and it does here."""
    kinds = ("key", "keyref", "unique")
    found = []
    for node in element:
        if not isinstance(node.tag, str) or local(node.tag) not in kinds:
            continue
        selector = node.find(q(XSD, "selector"))
        found.append(
            IdentityConstraint(
                kind=local(node.tag),
                name=node.get("name"),
                refer=node.get("refer"),
                selector=selector.get("xpath") if selector is not None else None,
                fields=tuple(
                    field.get("xpath") for field in node.findall(q(XSD, "field"))
                ),
            )
        )
    return tuple(found)


def _definition(element, catalogue):
    """The complexType behind an element: named via @type, or inline."""
    type_name = element.get("type")
    if type_name:
        info = catalogue.get(type_name)
        return info.node if info is not None else None
    for kind in ("complexType", "simpleType"):
        child = element.find(q(XSD, kind))
        if child is not None:
            return child
    return None


def _child_members(definition, catalogue, source, tree):
    """What sits directly below a type, as a list of members.

    A member is either an element declaration or a group that is worth showing.
    """
    groups = content_module.content_groups(definition, catalogue, source, tree.findings)
    members = []
    for group in groups:
        members.extend(_visible_members(group, group.compositor))
    return members


def _visible_members(group, compositor, in_choice=False):
    """Element declarations of a group, flattened, each with its constraints.

    Yields (declaration, compositor, is_alternative). Compositors are not
    nodes: in a tree, indentation means containment in an instance, and a
    compositor contains nothing. A node that belongs to a choice is marked
    instead, and the combinations are spelled out on the type page.
    """
    members = []
    for member in group.members:
        if isinstance(member, content_module.ChildGroup):
            members.extend(
                _visible_members(member, member.compositor, in_choice or member.compositor == "choice")
            )
        elif isinstance(member, content_module.Wildcard):
            # A wildcard has no name, so it has no instance path and no node.
            # The type page and the panel show it where it belongs, under the
            # type that allows it.
            continue
        else:
            members.append((member, compositor, in_choice))
    return members


def _content_holders(definition, catalogue, _guard=None):
    """The type itself plus its base types, nearest base last."""
    guard = _guard or set()
    if id(definition) in guard:
        return
    guard.add(id(definition))

    for container in ("complexContent", "simpleContent"):
        holder = definition.find(q(XSD, container))
        if holder is None:
            continue
        for kind in ("extension", "restriction"):
            derived = holder.find(q(XSD, kind))
            if derived is None:
                continue
            yield derived
            base = catalogue.get(derived.get("base") or "")
            if base is not None and base.node is not None:
                yield from _content_holders(base.node, catalogue, guard)
            return

    yield definition


def _occurs(value, default):
    if value is None:
        return default
    if value == "unbounded":
        return None
    try:
        return int(value)
    except ValueError:
        return default
