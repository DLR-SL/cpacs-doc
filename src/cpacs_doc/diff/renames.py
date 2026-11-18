"""Rename decisions: which removed node became which added node.

Decisions travel with the *new* schema, in a file next to it
(``cpacs_schema.renames.toml``). For a schema fetched from git that file is
read from the repository if it exists; decisions made here are written to
``renames/<variant>.toml`` in this project, to be copied upstream.

    [[rename]]                      # confirmed
    old = "refPoint"
    new = "referencePoint"
    parentType = "…"                # optional: only below this type

    [[reject]]                      # not a rename, never pair these again
    old = "settings"
    new = "setting"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: read the small subset this file uses
    tomllib = None
from pathlib import Path


@dataclass
class Decisions:
    confirm: dict[tuple[str | None, str], str] = field(default_factory=dict)
    reject: set[tuple[str | None, str, str]] = field(default_factory=set)

    def target(self, parent_type: str | None, old: str) -> str | None:
        return self.confirm.get((parent_type, old)) or self.confirm.get((None, old))

    def rejected(self, parent_type: str | None, old: str, new: str) -> bool:
        return (parent_type, old, new) in self.reject or (None, old, new) in self.reject

    def update(self, other: "Decisions") -> None:
        self.confirm.update(other.confirm)
        self.reject |= other.reject

    def set_confirm(self, old: str, new: str, parent_type: str | None = None) -> None:
        self.reject.discard((parent_type, old, new))
        self.confirm[(parent_type, old)] = new

    def set_reject(self, old: str, new: str, parent_type: str | None = None) -> None:
        if self.confirm.get((parent_type, old)) == new:
            del self.confirm[(parent_type, old)]
        self.reject.add((parent_type, old, new))


def forget(d: "Decisions", old: str, new: str, parent_type: str | None = None) -> None:
    """Drop a decision either way, so the pair is guessed again."""
    if d.confirm.get((parent_type, old)) == new:
        del d.confirm[(parent_type, old)]
    d.reject.discard((parent_type, old, new))


_TABLE = re.compile(r"^\[\[(rename|reject)\]\]\s*(#.*)?$")
_PAIR = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("(?:[^"\\]|\\.)*")\s*(#.*)?$')


def _loads_subset(text: str) -> dict:
    """``[[rename]]``/``[[reject]]`` tables of basic strings, as dump() writes them."""
    data: dict[str, list[dict]] = {"rename": [], "reject": []}
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _TABLE.match(line)
        if m:
            current = {}
            data[m.group(1)].append(current)
            continue
        m = _PAIR.match(line)
        if m and current is not None:
            current[m.group(1)] = json.loads(m.group(2))
            continue
        raise ValueError(f"renames file, line {number}: cannot read '{line}'")
    return data


def parse(text: str) -> Decisions:
    data = tomllib.loads(text) if tomllib else _loads_subset(text)
    d = Decisions()
    for r in data.get("rename", []):
        d.confirm[(r.get("parentType"), r["old"])] = r["new"]
    for r in data.get("reject", []):
        d.reject.add((r.get("parentType"), r["old"], r["new"]))
    return d


def load(texts: list[str]) -> Decisions:
    """Later texts win (upstream first, local file last)."""
    d = Decisions()
    for t in texts:
        d.update(parse(t))
    return d


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump(d: Decisions) -> str:
    out = ["# Rename decisions for this schema (see `cpacs-doc diff`).", ""]
    for (pt, old), new in sorted(d.confirm.items(), key=lambda x: (x[0][1], x[0][0] or "")):
        out += ["[[rename]]", f"old = {_q(old)}", f"new = {_q(new)}"]
        if pt:
            out.append(f"parentType = {_q(pt)}")
        out.append("")
    for pt, old, new in sorted(d.reject, key=lambda x: (x[1], x[2], x[0] or "")):
        out += ["[[reject]]", f"old = {_q(old)}", f"new = {_q(new)}"]
        if pt:
            out.append(f"parentType = {_q(pt)}")
        out.append("")
    return "\n".join(out)


def save(d: Decisions, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(d), encoding="utf-8")


def candidates(tree: dict) -> list[dict]:
    """Rename pairs in the merged tree, grouped by (old name, new name)."""
    groups: dict[tuple[str, str], dict] = {}

    def walk(n, path):
        here = f"{path}/{n['n']}"
        adds = {k["n"]: k for k in n["k"] if "ren" in k and k["s"] != "del"}
        for k in n["k"]:
            if n["s"] in ("add", "del"):
                break  # inside a whole added or removed subtree: nothing to pair
            if k["s"] == "del" and "ren" in k and k["ren"] in adds:
                a = adds[k["ren"]]
                g = groups.setdefault((k["n"], a["n"]), {
                    "old": k["n"], "new": a["n"], "oldType": k["t"], "newType": a["t"],
                    "confirmed": bool(a.get("rc")), "why": a.get("why", ""),
                    "parentTypes": [], "paths": [], "others": []})
                if n["t"] not in g["parentTypes"]:
                    g["parentTypes"].append(n["t"])
                g["paths"].append(here)
                if not g["others"]:
                    g["others"] = [x for x in adds if x != a["n"]]
        for k in n["k"]:
            walk(k, here)

    walk(tree, "")
    return sorted(groups.values(), key=lambda g: (g["confirmed"], -len(g["paths"]), g["old"]))


def unpaired(tree: dict) -> list[dict]:
    """Removed nodes without a partner next to added siblings: renames the heuristic missed."""
    out = []

    def walk(n, path):
        here = f"{path}/{n['n']}"
        adds = [k["n"] for k in n["k"] if k["s"] == "add" and "ren" not in k]
        for k in n["k"]:
            if n["s"] not in ("add", "del") and k["s"] == "del" and "ren" not in k and adds:
                out.append({"old": k["n"], "oldType": k["t"], "parentType": n["t"], "path": here, "adds": adds})
        for k in n["k"]:
            walk(k, here)

    walk(tree, "")
    return out
