"""Compatibility class of each change, seen from an existing CPACS file and the tools reading it.

* ``break``  – a file valid against the old schema can be invalid against the new one
  (removed, moved or renamed node, new required node, minOccurs up, maxOccurs down,
  enumeration value gone, element order now enforced).
* ``review`` – files stay valid only if their values fit, or tools reading new files must
  expect something new (type changed, node now optional or repeatable, other facets).
* ``ok``     – nothing to do (new optional node, documentation, new enumeration values).

Each changed node gets ``cx`` (the class), ``cr`` (the reasons) and, for renames and
moves, ``mg`` (migratable: a file can be converted mechanically). The highest class in a
subtree is kept as ``cxs`` for the viewer's filter.
"""
from __future__ import annotations

RANK = {None: 0, "ok": 1, "review": 2, "break": 3}


def _bounds(o: str) -> tuple[int, float]:
    lo, hi = o.split("..")
    return int(lo), float("inf") if hi == "∞" else int(hi)


def type_reasons(changes: list[dict]) -> list[tuple[str, str]]:
    """Reasons that come from inside a type and apply wherever the type is used."""
    out = []
    for c in changes:
        w, m = c["what"], c.get("member")
        if w == "facet" and m == "enumeration":
            old = {v.get("value") for v in c.get("old") or []}
            new = {v.get("value") for v in c.get("new") or []}
            gone, came = sorted(old - new), sorted(new - old)
            if gone:
                out.append(("break", "enumeration values removed: " + ", ".join(gone)))
            if came:
                out.append(("ok", "enumeration values added: " + ", ".join(came)))
        elif w == "facet":
            out.append(("review", f"restriction '{m}' changed"))
        elif w == "compositor" and not m:
            if c.get("new") == "sequence" and c.get("old") != "sequence":
                out.append(("break", f"compositor {c.get('old')} → sequence: element order is now enforced"))
            else:
                out.append(("review", f"compositor {c.get('old')} → {c.get('new')}"))
        elif w == "base" and not m:
            out.append(("review", f"base type {c.get('old')} → {c.get('new')}"))
    return out


def choice_of(n: dict, parent: dict | None) -> str | None:
    """The group path of the outermost choice n sits in, if any: then n is one alternative,
    never required on its own."""
    if parent is None or not n.get("gp"):
        return None
    gc = parent.get("gc") or {}
    parts = n["gp"].split(".")
    for i in range(1, len(parts) + 1):
        if gc.get(".".join(parts[:i])) == "choice":
            return ".".join(parts[:i])
    return None


def _old_alternative(choice: str, parent: dict) -> bool:
    """Whether the choice had an alternative before, i.e. old files already chose one."""
    return any(k["s"] != "add" and (k.get("gp") or "") .split("~")[0].startswith(choice) for k in parent["k"])


def node_reasons(n: dict, parent: dict | None, type_changes: dict) -> tuple[list, bool]:
    r: list[tuple[str, str]] = []
    mg = False
    s = n["s"]
    if s == "del" and "ren" not in n:
        if parent is not None and parent["s"] == "del":
            return [], False  # part of a removed subtree; its top carries the class
        r.append(("break", "removed: old files that use it become invalid"))
    elif s == "add" and "ren" not in n:
        if parent is not None and parent["s"] == "add":
            return [], False  # part of a new subtree; its top carries the class
        lo, _ = _bounds(n["o"])
        choice = choice_of(n, parent)
        if lo >= 1 and choice and _old_alternative(choice, parent):
            r.append(("ok", "new alternative in an existing choice"))
        elif lo >= 1 and choice:
            r.append(("break", "new required choice: old files have none of its alternatives"))
        elif lo >= 1:
            r.append(("break", "new required node: old files lack it"))
        else:
            r.append(("ok", "new optional node"))
    if "ren" in n and s != "del":
        r.append(("break", f"renamed from {n['ren']}: old files use the old name"))
        mg = True
    if "mv" in n:
        r.append(("break", f"moved from {n['mv']}: old files have it at the old place"))
        mg = True
    if "oo" in n:
        (lo0, hi0), (lo1, hi1) = _bounds(n["oo"]), _bounds(n["o"])
        if lo1 > lo0 and not choice_of(n, parent):
            r.append(("break", f"now required ({n['oo']} → {n['o']})"))
        if hi1 < hi0:
            r.append(("break", f"fewer occurrences allowed ({n['oo']} → {n['o']})"))
        if lo1 < lo0:
            r.append(("review", f"now optional ({n['oo']} → {n['o']}): readers must handle its absence"))
        if hi1 > hi0:
            r.append(("review", f"may now repeat ({n['oo']} → {n['o']}): readers must handle several"))
    if "ot" in n:
        r.append(("review", f"type {n['ot']} → {n['t']}: check that existing values fit"))
    for a in n.get("at", []):
        req = a["u"] == "required"
        if a["s"] == "add":
            r.append(("break", f"new required attribute @{a['n']}: old files lack it") if req
                     else ("ok", f"new optional attribute @{a['n']}"))
        elif a["s"] == "del":
            r.append(("break", f"attribute @{a['n']} removed: old files that use it become invalid"))
        elif a["s"] == "mod":
            if "ou" in a and req:
                r.append(("break", f"attribute @{a['n']} now required"))
            elif "ou" in a:
                r.append(("review", f"attribute @{a['n']} now optional: readers must handle its absence"))
            if "ot" in a:
                r.append(("review", f"attribute @{a['n']} type {a['ot']} → {a['t']}: check that existing values fit"))
            if "od" in a or "of" in a:
                r.append(("review", f"attribute @{a['n']} default or fixed value changed"))
        elif a["s"] == "doc" and not r:
            r.append(("ok", f"documentation of @{a['n']} changed"))
    if s in ("same", "mod", "doc") and n.get("t") in type_changes:
        r += type_reasons(type_changes[n["t"]])
    if s == "doc" and not r:
        r.append(("ok", "documentation changed"))
    return r, mg


def annotate(tree: dict, types_diff: dict) -> dict:
    """Set cx/cr/mg/cxs on the tree; return counts per class."""
    counts = {"break": 0, "review": 0, "ok": 0, "migratable": 0}
    changed_types = types_diff.get("changed", {})

    def walk(n, parent):
        reasons, mg = node_reasons(n, parent, changed_types)
        worst = None
        if reasons:
            reasons.sort(key=lambda r: -RANK[r[0]])   # the worst reason first
            worst = reasons[0][0]
            n["cx"], n["cr"] = worst, [t for _, t in reasons]
            counts[worst] += 1
            if mg:
                n["mg"] = True
                counts["migratable"] += 1
        for k in n["k"]:
            sub = walk(k, n)
            if RANK[sub] > RANK[worst]:
                worst = sub
        if worst:
            n["cxs"] = worst
        return worst

    walk(tree, None)
    return counts


def breaking_list(tree: dict) -> list[dict]:
    out = []

    def walk(n, path):
        here = f"{path}/{n['n']}"
        if n.get("cx") in ("break", "review"):
            out.append({"path": here, "class": n["cx"], "reasons": n["cr"], "migratable": bool(n.get("mg"))})
        for k in n["k"]:
            walk(k, here)

    walk(tree, "")
    return out
