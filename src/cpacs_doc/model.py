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

from lxml import etree

from . import renderer
from .annotations import DDUE, Documentation

MODEL_VERSION = "1.0"


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


def _child_entry(child) -> dict:
    entry = {
        "name": child.name,
        "type": child.type_name,
        "minOccurs": child.min_occurs,
        "maxOccurs": child.max_occurs,
        "compositor": child.compositor,
        "line": child.line,
    }
    documentation = _documentation(child.doc)
    if documentation:
        entry["documentation"] = documentation
    return entry


def _declaration_entry(node) -> dict:
    entry = {
        "name": node.name,
        "type": node.type_name,
        "minOccurs": node.min_occurs,
        # null encodes unbounded; a sentinel integer would be
        # indistinguishable from a real bound.
        "maxOccurs": node.max_occurs,
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
    return str(node.line) if node.line else f"{node.type_name}:{node.name}"


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
class RenderedDocumentation:
    summary: str = ""
    remarks: str = ""


def render_all(catalogue, media_catalogue, source: str) -> tuple[dict[str, RenderedDocumentation], list]:
    """Render every type's documentation once, for both the pages and the model.

    Rendering here rather than in the viewer keeps one implementation of the
    vocabulary. The asset prefix is left empty: the generator writes pages at a
    known depth below the output root, so image sources stay relative and the
    whole output directory remains movable.
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
        remarks = renderer.render(info.doc.remarks, context)
        if summary or remarks:
            rendered[name] = RenderedDocumentation(summary=summary, remarks=remarks)
    return rendered, context.findings


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
            "distinctPaths": tree.distinct_paths,
            "maxDepth": tree.max_depth,
            "recursionCuts": tree.recursion_cuts,
            "declarations": len(declarations),
            "attributes": sum(len(c.attributes) for c in content_by_type.values()),
            "enumerationValues": sum(len(c.enumeration) for c in content_by_type.values()),
            "mediaEntries": len(media_catalogue.entries) if media_catalogue else 0,
        },
        "types": {
            name: _type_entry(info, content_by_type.get(name), rendered.get(name))
            for name, info in sorted(catalogue.types.items())
        },
        "declarations": declarations,
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
    temporary.write_text(
        json.dumps(model, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
