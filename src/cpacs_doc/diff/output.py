"""Write the comparison: diff.json, report.md and the self-contained diff.html."""
from __future__ import annotations

import json
from datetime import date
from importlib import resources
from pathlib import Path

from .typediff import describe
from .typemap import note_for

HEAD = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        "<title>{title}</title></head><body>\n")


def _pooled(tree: dict) -> tuple[dict, list]:
    """Copy of the tree whose repeated texts (documentation, attribute lists) are replaced
    by indices into one pool. A type used in many places repeats them at every place."""
    pool: list = []
    index: dict[str, int] = {}

    def ref(value) -> int:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in index:
            index[key] = len(pool)
            pool.append(value)
        return index[key]

    def walk(n):
        r = {k: v for k, v in n.items() if k not in ("k", "d", "od", "at", "cr", "gc")}
        for k in ("d", "od", "at", "cr", "gc"):
            if k in n:
                r[k] = ref(n[k])
        r["k"] = [walk(c) for c in n["k"]]
        return r

    return walk(tree), pool


def viewer_payload(result: dict) -> dict:
    tc = {}
    for name, changes in result["types"]["changed"].items():
        inner = [describe(c) for c in changes if c["what"] not in ("added", "removed")]
        if inner:
            tc[name] = inner
    t, p = result["types"], result["paths"]
    tree, pool = _pooled(result["tree"])
    notes = {}
    for e in result.get("typeMap", []):
        for o in e["old"]:
            for n in e["new"]:
                notes[f"{o}>{n}"] = note_for(e)
    return {
        "typeNotes": notes,
        "meta": result["meta"],
        "tree": tree,
        "pool": pool,
        "hot": result["hotspots"],
        "typeChanges": tc,
        "stats": {"typesAdded": len(t["added"]), "typesRemoved": len(t["removed"]),
                  "typesChanged": len(t["changed"]), "pathsAdded": p["add"],
                  "pathsRemoved": p["del"], "pathsChanged": p["mod"], "pathsDoc": p["doc"],
                  "renames": p["renames"], "moves": p["moves"],
                  "breaking": result["compat"]["counts"]["break"], "review": result["compat"]["counts"]["review"],
                  "compatible": result["compat"]["counts"]["ok"],
                  "migratable": result["compat"]["counts"]["migratable"]},
    }


def write_html(result: dict, path: Path) -> None:
    template = resources.files("cpacs_doc").joinpath("assets/diff.html").read_text(encoding="utf-8")
    data = "window.DIFF=" + json.dumps(viewer_payload(result), separators=(",", ":"), ensure_ascii=False) + ";"
    data = data.replace("</", "<\\/")
    m = result["meta"]
    page = HEAD.format(title=f"Schema diff {m['old']} → {m['new']}") + template.replace("/*DATA*/", data) + "\n</body></html>\n"
    path.write_text(page, encoding="utf-8")


def write_report(result: dict, path: Path) -> None:
    m, t, p = result["meta"], result["types"], result["paths"]
    lines = [f"# Schema diff: {m['old']} → {m['new']}", "",
             f"- old: {m['oldOrigin']}", f"- new: {m['newOrigin']}", f"- generated: {m['generated']}", "",
             "## Summary", "",
             f"- Types: +{len(t['added'])} added, −{len(t['removed'])} removed, ~{len(t['changed'])} changed",
             f"- Paths in the instance tree: +{p['add']} added, −{p['del']} removed, "
             f"~{p['mod']} type or cardinality changed, {p['doc']} documentation only",
             f"- Renames (confirmed or suspected): {p['renames']}",
             f"- Moved nodes: {p['moves']}", ""]
    cc = result["compat"]["counts"]
    lines += ["## Compatibility", "",
              f"- breaking: {cc['break']} (of them {cc['migratable']} renames or moves that can be migrated mechanically)",
              f"- to review: {cc['review']}", f"- compatible: {cc['ok']}", "",
              "Breaking: a file valid against the old schema can be invalid against the new one. "
              "To review: valid only if the values fit, or readers must expect something new.", ""]
    for cls, title in (("break", "### Breaking"), ("review", "### To review")):
        rows = [c for c in result["compat"]["changes"] if c["class"] == cls]
        if rows:
            lines += [title, ""]
            lines += [f"- `{c['path']}`{' (migratable)' if c['migratable'] else ''}: " + "; ".join(c["reasons"])
                      for c in rows]
            lines.append("")
    if result.get("moves"):
        lines += ["## Moves", ""]
        lines += [f"- `{mv['from']}` → `{mv['to']}`" for mv in result["moves"]]
        lines.append("")
    if result["renames"]:
        lines += ["## Renames", ""]
        lines += [f"- `{r['path']}`: `{r['old']}` → `{r['new']}`{'' if r['confirmed'] else ' (suspected)'}"
                  for r in result["renames"]]
        lines.append("")
    if result.get("typeMap"):
        lines += ["## Renamed, merged and split types", ""]
        for e in result["typeMap"]:
            lines.append(f"- {note_for(e)} ({e['places']} places)")
            for o, ch in e["changes"].items():
                lines += [f"  - `{describe(c)}`" + (f" (from {o})" if len(e["old"]) > 1 else "")
                          for c in ch if c["what"] != "documentation"]
        lines.append("")
    lines += ["## Added types", ""] + [f"- `{n}`" for n in t["added"]] + [""]
    lines += ["## Removed types", ""] + [f"- `{n}`" for n in t["removed"]] + [""]
    lines += ["## Changed types", ""]
    for name, changes in t["changed"].items():
        lines.append(f"### `{name}`")
        lines += [f"- `{describe(c)}`" for c in changes]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


SUMMARY_LIMIT = 60000   # GitHub comments take 65536 characters


def _short(path: str) -> str:
    parts = path.strip("/").split("/")
    return "/".join(parts) if len(parts) <= 4 else "…/" + "/".join(parts[-3:])


def write_summary(result: dict, path: Path, link: str | None = None, per_group: int = 8) -> None:
    """A short Markdown summary for a pull request comment: counts, breaking changes grouped
    by reason, renames, moves and type changes, each list cut after a few entries."""
    m, t, p, cc = result["meta"], result["types"], result["paths"], result["compat"]["counts"]
    lines = [f"### CPACS schema diff: `{m['old']}` → `{m['new']}`", ""]
    if link:
        lines += [f"[Open the diagram]({link})", ""]
    if not (t["added"] or t["removed"] or t["changed"]):
        path.write_text("\n".join(lines + ["No structural or documentation changes."]) + "\n", encoding="utf-8")
        return
    lines += [f"**{cc['break']} breaking** ({cc['migratable']} migratable) · {cc['review']} to review · "
              f"{cc['ok']} compatible",
              "",
              f"Types +{len(t['added'])} −{len(t['removed'])} ~{len(t['changed'])} · "
              f"paths +{p['add']} −{p['del']} · {p['moves']} moved · {p['renames']} renamed", ""]
    groups: dict[str, list[str]] = {}
    for c in result["compat"]["changes"]:
        if c["class"] != "break":
            continue
        key = c["reasons"][0].split(":")[0].split(" (")[0]
        key = "renamed" if key.startswith("renamed") else "moved" if key.startswith("moved") else key
        groups.setdefault(key, []).append(c["path"])
    if groups:
        lines += ["<details><summary>Breaking changes</summary>", ""]
        for key, paths in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            shorts: dict[str, int] = {}
            for x in paths:
                shorts[_short(x)] = shorts.get(_short(x), 0) + 1
            items = [f"`{s}`" + (f" ×{n}" if n > 1 else "") for s, n in shorts.items()]
            lines.append(f"- **{key}** ({len(paths)}): " + ", ".join(items[:per_group])
                         + (f" and {len(items) - per_group} more" if len(items) > per_group else ""))
        lines += ["", "</details>", ""]
    if result.get("typeMap"):
        lines += ["<details><summary>Renamed and merged types</summary>", ""]
        lines += [f"- {note_for(e)}" for e in result["typeMap"][:per_group * 2]]
        lines += ["", "</details>", ""]
    text = "\n".join(lines)
    if len(text) > SUMMARY_LIMIT:
        text = text[:SUMMARY_LIMIT].rsplit("\n", 1)[0] + "\n\n… (cut; see report.md)\n"
    path.write_text(text, encoding="utf-8")


def collect_renames(tree: dict) -> list[dict]:
    out = []

    def walk(n, path):
        here = f"{path}/{n['n']}"
        if n["s"] != "del" and "ren" in n:
            out.append({"path": path, "old": n["ren"], "new": n["n"], "confirmed": bool(n.get("rc"))})
        for k in n["k"]:
            walk(k, here)

    walk(tree, "")
    return out


def collect_moves(tree: dict) -> list[dict]:
    out = []

    def walk(n, path):
        here = f"{path}/{n['n']}"
        if "mv" in n:
            out.append({"from": n["mv"], "to": here})
        for k in n["k"]:
            walk(k, here)

    walk(tree, "")
    return out


def today() -> str:
    return date.today().isoformat()
