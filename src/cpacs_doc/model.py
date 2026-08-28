"""Serialisation of the intermediate model.

Holds what the extractor knows without rendering anything: the type catalogue,
the instance tree, the media catalogue and the build report. `ddue` markup is
carried as plain text only — turning it into HTML is the generator's job, and
doing it here would freeze rendering decisions into the model format.

`meta.modelVersion` is the contract with every consumer (N15). Breaking changes
increment the major version.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import re
from copy import deepcopy

from lxml import etree

from . import renderer
from .annotations import DDUE, Documentation

MODEL_VERSION = "1.2"


def flatten(node: etree._Element | None) -> str:
    """Text content of a ddue subtree, whitespace normalised.

    Lossy by design: the markup is preserved in the schema, and the renderer
    reads it from there. The model carries text so the report and the search
    index have something to work with.
    """
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _documentation(doc: Documentation, html: "RenderedDocumentation | None" = None) -> dict:
    """Only non-empty fields. Most nodes document nothing, and empty keys
    repeated across 54,552 nodes dominate the file size.

    `html` carries the rendered fragments where a renderer was supplied. Text
    and HTML sit side by side rather than one replacing the other: search and
    diff work on the text, the viewer inserts the HTML, and a consumer that
    wants neither can ignore both.
    """
    entry = {}
    summary = flatten(doc.summary)
    remarks = flatten(doc.remarks)
    if summary:
        entry["summary"] = summary
    if remarks:
        entry["remarks"] = remarks
    if doc.text:
        entry["text"] = doc.text
    if doc.image_ids:
        entry["imageIds"] = sorted(doc.image_ids)
    if doc.ddue_elements:
        entry["ddueElements"] = sorted(doc.ddue_elements)
    if html is not None:
        if html.summary:
            entry["summaryHtml"] = html.summary
        if html.remarks:
            entry["remarksHtml"] = html.remarks
    return entry


def _type_entry(info, content, html) -> dict:
    entry = {
        "name": info.name,
        "kind": info.kind,
        "anonymous": info.anonymous,
        "base": info.base,
        "derivation": info.derivation,
        "compositor": info.compositor,
        "line": info.line,
        "documentation": _documentation(info.doc, html),
    }
    if content is not None:
        if content.attributes:
            entry["attributes"] = [_attribute_entry(a) for a in content.attributes]
        if content.enumeration:
            entry["enumeration"] = [_enumeration_entry(v) for v in content.enumeration]
        if content.facets:
            entry["facets"] = [
                {"name": f.name, "value": f.value, "line": f.line} for f in content.facets
            ]
        if content.children:
            entry["children"] = [_child_entry(c) for c in content.children]
    return entry


def _attribute_entry(attribute) -> dict:
    entry = {
        "name": attribute.name,
        "type": attribute.type_name,
        "use": attribute.use,
        "declaredIn": attribute.declared_in,
        "inherited": attribute.inherited,
        "line": attribute.line,
    }
    if attribute.default is not None:
        entry["default"] = attribute.default
    if attribute.fixed is not None:
        entry["fixed"] = attribute.fixed
    documentation = _documentation(attribute.doc)
    if documentation:
        entry["documentation"] = documentation
    return entry


def _enumeration_entry(value) -> dict:
    entry = {"value": value.value, "line": value.line}
    documentation = _documentation(value.doc)
    if documentation:
        entry["documentation"] = documentation
    return entry


def _child_entry(member) -> dict:
    """One row of the child table: an element, or a compositor with members.

    `kind` distinguishes them so a consumer does not have to guess from the
    presence of a key.
    """
    if hasattr(member, "compositor"):
        return {
            "kind": "group",
            "compositor": member.compositor,
            "minOccurs": member.min_occurs,
            "maxOccurs": member.max_occurs,
            "members": [_child_entry(m) for m in member.members],
        }
    entry = {
        "kind": "element",
        "name": member.name,
        "type": member.type_name,
        "minOccurs": member.min_occurs,
        "maxOccurs": member.max_occurs,
        **({"default": member.default} if member.default is not None else {}),
        **({"fixed": member.fixed} if member.fixed is not None else {}),
        "line": member.line,
    }
    documentation = _documentation(member.doc)
    if documentation:
        entry["documentation"] = documentation
    return entry


def _declaration_entry(node) -> dict:
    entry = {
        "name": node.name,
        **({"alternative": True} if node.alternative else {}),
        "type": node.type_name,
        "minOccurs": node.min_occurs,
        # null encodes unbounded; a sentinel integer would be
        # indistinguishable from a real bound.
        "maxOccurs": node.max_occurs,
        **({"default": node.default} if node.default is not None else {}),
        **({"fixed": node.fixed} if node.fixed is not None else {}),
        "compositor": node.compositor,
        "line": node.line,
    }
    documentation = _documentation(node.doc)
    if documentation:
        entry["documentation"] = documentation
    return entry


def _declaration_key(node) -> str:
    """Identifies one element declaration in the schema.

    A declaration is expanded once per path it is reachable on — an element
    below a widely reused type appears hundreds of times. Everything except
    path and depth belongs to the declaration, not to the occurrence, so the
    tree references declarations instead of repeating them. Path and depth are
    recoverable from the tree structure itself.
    """
    # Two declarations at the same line cannot differ; the alternative flag is
    # a property of the declaration's position, so it is part of the key.
    base = str(node.line) if node.line else f"{node.type_name}:{node.name}"
    return f"{base}a" if node.alternative else base


def _collect_declarations(node, into: dict) -> None:
    key = _declaration_key(node)
    if key not in into:
        into[key] = _declaration_entry(node)
    for child in node.children:
        _collect_declarations(child, into)


def _node_entry(node) -> dict:
    entry = {"d": _declaration_key(node)}
    if node.recursive:
        entry["recursive"] = True
    if node.children:
        entry["children"] = [_node_entry(c) for c in node.children]
    return entry


@dataclass(frozen=True)
class Section:
    """One titled `ddue:section`, addressable on its own."""

    title: str
    slug: str
    html: str
    text: str


@dataclass(frozen=True)
class RenderedDocumentation:
    summary: str = ""
    remarks: str = ""
    sections: tuple[Section, ...] = ()


_SLUG = re.compile(r"[^a-z0-9]+")


def section_slug(title: str) -> str:
    """A file-safe address for a section, from its title and nothing else.

    Mechanical on purpose. Dropping the chapter number would leave the tool
    deciding what part of a heading is meaningful, and the number could then
    change without the address noticing.
    """
    return _SLUG.sub("-", title.lower()).strip("-") or "section"


def _named(node, name: str):
    """Direct children of `node` with that local name, comments skipped."""
    return [child for child in node
            if isinstance(child.tag, str) and etree.QName(child).localname == name]


def _split_sections(remarks, context) -> tuple[str, tuple[Section, ...]]:
    """Render a remarks body as its titled sections plus what surrounds them.

    The general documentation of a schema is a document: 31 sections in CPACS
    3.5.1, 5,720 words, all direct children of one `content`. Rendered as one
    fragment it can only be read by scrolling the node it hangs off. Split, each
    section has an address, a page and a place in a list.

    A section that is not titled stays where it is: it has no name to be listed
    under, and removing it from the body would lose it.
    """
    if remarks is None:
        return "", ()
    content = _named(remarks, "content")
    container = content[0] if content else remarks
    nodes = _named(container, "section")
    if not nodes:
        return renderer.render(remarks, context), ()

    sections: list[Section] = []
    taken: set[str] = set()
    lifted: set[int] = set()
    for node in nodes:
        titles = _named(node, "title")
        title = flatten(titles[0]) if titles else ""
        if not title:
            context.report(
                "warning",
                "SECTION_WITHOUT_TITLE",
                "ddue:section without a title; it stays in the body and gets no page",
                node,
            )
            continue
        name = section_slug(title)
        if name in taken:
            context.report(
                "warning",
                "SECTION_ADDRESS_TAKEN",
                f"two sections resolve to the address {name!r}: {title!r}",
                node,
            )
            suffix = 2
            while f"{name}-{suffix}" in taken:
                suffix += 1
            name = f"{name}-{suffix}"
        taken.add(name)
        lifted.add(container.index(node))

        # The title heads the page and the list entry, so it is not repeated
        # inside the body.
        body = deepcopy(node)
        for child in _named(body, "title"):
            body.remove(child)
        sections.append(
            Section(title=title, slug=name,
                    html=renderer.render(body, context), text=flatten(node))
        )

    rest = deepcopy(remarks)
    rest_content = _named(rest, "content")
    rest_container = rest_content[0] if rest_content else rest
    for index in sorted(lifted, reverse=True):
        del rest_container[index]
    return renderer.render(rest, context), tuple(sections)


def render_all(catalogue, media_catalogue, source: str, *,
               sections_for: str | None = None) -> tuple[dict[str, RenderedDocumentation], list]:
    """Render every type's documentation once, for both the pages and the model.

    Rendering here rather than in the viewer keeps one implementation of the
    vocabulary. Image sources carry the renderer's root placeholder, which each
    consumer resolves against its own depth: the same fragment is used by type
    pages and by the viewer, and neither may bake in a deployment location.
    """
    entries = (
        {image_id: {"file": entry.file, "alt": entry.alt}
         for image_id, entry in media_catalogue.entries.items()}
        if media_catalogue is not None
        else None
    )
    context = renderer.RenderContext(media=entries, source=source)
    rendered: dict[str, RenderedDocumentation] = {}
    for name, info in catalogue.types.items():
        context.owner = f"{info.kind} {name}"
        summary = renderer.render(info.doc.summary, context)
        # Only the type the documentation hangs off is split. Eleven other types
        # carry two to four sections apiece, where they are headings within a
        # description rather than chapters of a document.
        if name == sections_for:
            remarks, sections = _split_sections(info.doc.remarks, context)
        else:
            remarks, sections = renderer.render(info.doc.remarks, context), ()
        if summary or remarks or sections:
            rendered[name] = RenderedDocumentation(
                summary=summary, remarks=remarks, sections=sections
            )
    return rendered, context.findings


def _documentation_entry(tree, rendered) -> dict:
    """The general documentation: the sections of the root element's type.

    A top-level key rather than something to be dug out of `types`, because
    neither the generator nor the viewer should have to know which type that is
    to find the handbook.
    """
    name = tree.root.type_name if tree.root else None
    entry = rendered.get(name) if name else None
    if entry is None or not entry.sections:
        return {}
    return {
        "type": name,
        "sections": [
            {"title": s.title, "slug": s.slug, "html": s.html, "text": s.text}
            for s in entry.sections
        ],
    }


def _first_paths(tree) -> dict[str, str]:
    """First instance path at which each type appears.

    Lets a static type page offer a way back into the tree. 1,100 of the 1,206
    catalogue entries are reachable this way; the rest are anonymous inline
    types that never appear as an element's type, and they simply get no entry
    rather than a fabricated one.
    """
    paths: dict[str, str] = {}
    if not tree.root:
        return paths
    stack = [(tree.root, [])]
    while stack:
        node, prefix = stack.pop()
        path = prefix + [node.name]
        if node.type_name and node.type_name not in paths:
            paths[node.type_name] = "/".join(path)
        for child in reversed(node.children):
            stack.append((child, path))
    return paths


def build(
    catalogue,
    tree,
    media_catalogue,
    report,
    *,
    schema_path: str,
    schema_version: str | None,
    content_by_type: dict | None = None,
    rendered: dict[str, RenderedDocumentation] | None = None,
) -> dict:
    declarations: dict[str, dict] = {}
    if tree.root:
        _collect_declarations(tree.root, declarations)
    content_by_type = content_by_type or {}
    rendered = rendered or {}

    return {
        "meta": {
            "modelVersion": MODEL_VERSION,
            "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "schemaPath": schema_path,
            "schemaVersion": schema_version,
        },
        "statistics": {
            "types": len(catalogue.types),
            "documentedTypes": sum(1 for t in catalogue.types.values() if t.documented),
            "treeNodes": tree.nodes,
            "treeAlternatives": tree.alternatives,
            "distinctPaths": tree.distinct_paths,
            "maxDepth": tree.max_depth,
            "recursionCuts": tree.recursion_cuts,
            "declarations": len(declarations),
            "attributes": sum(len(c.attributes) for c in content_by_type.values()),
            "enumerationValues": sum(len(c.enumeration) for c in content_by_type.values()),
            "valueConstraints": sum(len(c.facets) for c in content_by_type.values()),
            "mediaEntries": len(media_catalogue.entries) if media_catalogue else 0,
        },
        "types": {
            name: _type_entry(info, content_by_type.get(name), rendered.get(name))
            for name, info in sorted(catalogue.types.items())
        },
        "declarations": declarations,
        "documentation": _documentation_entry(tree, rendered),
        "firstPaths": _first_paths(tree),
        "tree": _node_entry(tree.root) if tree.root else None,
        "media": {
            image_id: {"file": entry.file, "alt": entry.alt}
            for image_id, entry in sorted(media_catalogue.entries.items())
        }
        if media_catalogue
        else {},
        "report": report.to_json(),
    }


def write(model: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written via a temporary file so an interrupted run cannot leave a
    # half-written model that a later stage would happily parse.
    temporary = path.with_suffix(path.suffix + ".tmp")
    # Written compact: it is a generated artefact that is parsed, not read, and
    # indentation costs a factor of about four in transfer size.
    temporary.write_text(
        json.dumps(model, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
