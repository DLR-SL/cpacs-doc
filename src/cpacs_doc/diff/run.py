"""The diff pipeline: two schemas in, the four files out."""
from __future__ import annotations

import json
from pathlib import Path

from .. import cli as cli_module
from .. import model as model_module
from ..findings import Report
from . import compat, output, renames, treediff, typediff, typemap

RENAMES_SUFFIX = ".renames.toml"


def build_model(schema_path: Path) -> dict:
    """The model of one schema, as `build` writes it, without media."""
    report = Report()
    catalogue, tree, media_catalogue, content_by_type = cli_module.run(
        schema_path, None, report, media_expected=False)
    rendered, render_findings = model_module.render_all(
        catalogue, media_catalogue, schema_path.name,
        sections_for=tree.root.type_name if tree.root else None)
    report.extend(render_findings)
    return model_module.build(
        catalogue, tree, media_catalogue, report,
        schema_path=str(schema_path),
        schema_version=cli_module.root_version(schema_path, report),
        content_by_type=content_by_type, rendered=rendered)


def renames_beside(schema_path: Path) -> Path:
    return schema_path.with_name(schema_path.stem + RENAMES_SUFFIX)


def _label(path: Path) -> str:
    return path.stem if path.stem != "cpacs_schema" else (path.parent.name or path.stem)


def diff(old_path: Path, new_path: Path, out: Path, *, old_label: str | None = None,
         new_label: str | None = None, renames_path: Path | None = None, link: str | None = None) -> dict:
    """Compare and write; returns the result that diff.json holds."""
    m_old, m_new = build_model(old_path), build_model(new_path)
    renames_path = renames_path or renames_beside(new_path)
    decisions = renames.load([renames_path.read_text(encoding="utf-8")] if renames_path.exists() else [])
    tree = treediff.merge(m_old, m_new, decisions)
    types = typediff.diff_types(m_old, m_new)
    counts = compat.annotate(tree, types)
    result = {
        "meta": {"old": old_label or _label(old_path), "new": new_label or _label(new_path),
                 "oldOrigin": str(old_path), "newOrigin": str(new_path), "generated": output.today(),
                 "renamesFile": str(renames_path) if renames_path.exists() else None},
        "types": types,
        "compat": {"counts": counts, "changes": compat.breaking_list(tree)},
        "typeMap": typemap.type_map(tree, types, m_old["types"], m_new["types"]),
        "paths": treediff.path_stats(tree),
        "hotspots": treediff.hotspots(tree),
        "renames": output.collect_renames(tree),
        "moves": output.collect_moves(tree),
        "tree": tree,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "diff.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    output.write_report(result, out / "report.md")
    output.write_summary(result, out / "summary.md", link)
    output.write_html(result, out / "diff.html")
    return result
