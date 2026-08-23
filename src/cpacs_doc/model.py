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
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

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


def _documentation(doc: Documentation) -> dict:
    """Only non-empty fields. Most nodes document nothing, and empty keys
    repeated across 54,552 nodes dominate the file size."""
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
    return entry


def _type_entry(info) -> dict:
    return {
        "name": info.name,
        "kind": info.kind,
        "anonymous": info.anonymous,
        "base": info.base,
        "derivation": info.derivation,
        "compositor": info.compositor,
        "line": info.line,
        "documentation": _documentation(info.doc),
    }


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


def build(catalogue, tree, media_catalogue, report, *, schema_path: str, schema_version: str | None) -> dict:
    declarations: dict[str, dict] = {}
    if tree.root:
        _collect_declarations(tree.root, declarations)

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
            "mediaEntries": len(media_catalogue.entries) if media_catalogue else 0,
        },
        "types": {name: _type_entry(info) for name, info in sorted(catalogue.types.items())},
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
