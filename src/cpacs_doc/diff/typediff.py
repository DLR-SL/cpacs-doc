"""Compare the type catalogues of two cpacs-doc models.

Types are matched by name. Declaration ids in the model are line numbers and
are never used for matching.
"""
from __future__ import annotations

import json

COMPARED = ("kind", "base", "derivation", "compositor")
MEMBER_FIELDS = ("type", "minOccurs", "maxOccurs", "use", "default", "fixed")
IGNORED = {"line", "declaredIn", "documentation", "children", "attributes", "name", "anonymous"}


def _doc(o: dict) -> str:
    return json.dumps(o.get("documentation"), sort_keys=True)


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in ("line", "declaredIn")}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def members(t: dict) -> dict[str, dict]:
    """Elements (``el:name``), other content (``any:i``) and own attributes (``@name``)."""
    out: dict[str, dict] = {}

    def walk(ms):
        for i, m in enumerate(ms):
            if m.get("kind") == "element":
                out["el:" + m["name"]] = m
            elif m.get("kind") == "group":
                walk(m.get("members", []))
            else:
                out[f"{m.get('kind')}:{i}"] = m

    walk(t.get("children", []))
    for a in t.get("attributes", []):
        if not a.get("inherited"):
            out["@" + a["name"]] = a
    return out


def compare_type(a: dict, b: dict) -> list[dict]:
    """Changes of one type, each ``{"what", "member"?, "old"?, "new"?}``."""
    ch: list[dict] = []
    for k in COMPARED:
        if a.get(k) != b.get(k):
            ch.append({"what": k, "old": a.get(k), "new": b.get(k)})
    ma, mb = members(a), members(b)
    for k in mb.keys() - ma.keys():
        ch.append({"what": "added", "member": k, "new": mb[k].get("type")})
    for k in ma.keys() - mb.keys():
        ch.append({"what": "removed", "member": k, "old": ma[k].get("type")})
    for k in sorted(ma.keys() & mb.keys()):
        x, y = ma[k], mb[k]
        for f in MEMBER_FIELDS:
            if x.get(f) != y.get(f):
                ch.append({"what": f, "member": k, "old": x.get(f), "new": y.get(f)})
        if _doc(x) != _doc(y):
            ch.append({"what": "documentation", "member": k})
    sa = {k: v for k, v in _strip(a).items() if k not in IGNORED and k not in COMPARED}
    sb = {k: v for k, v in _strip(b).items() if k not in IGNORED and k not in COMPARED}
    for k in sorted(sa.keys() | sb.keys()):
        if json.dumps(sa.get(k), sort_keys=True) != json.dumps(sb.get(k), sort_keys=True):
            ch.append({"what": "facet", "member": k, "old": sa.get(k), "new": sb.get(k)})
    if _doc(a) != _doc(b):
        ch.append({"what": "documentation"})
    ch.sort(key=lambda c: (c["what"], c.get("member", "")))
    return ch


def diff_types(old: dict, new: dict) -> dict:
    ta, tb = old["types"], new["types"]
    changed = {}
    for n in sorted(ta.keys() & tb.keys()):
        c = compare_type(ta[n], tb[n])
        if c:
            changed[n] = c
    return {
        "added": sorted(tb.keys() - ta.keys()),
        "removed": sorted(ta.keys() - tb.keys()),
        "changed": changed,
    }


def describe(c: dict) -> str:
    m = c.get("member", "")
    w = c["what"]
    if w == "added":
        return f"+ {m} : {c['new']}"
    if w == "removed":
        return f"- {m} : {c['old']}"
    if w == "documentation":
        return f"~ {m + '.' if m else ''}documentation"
    if w == "facet":
        return f"~ {m}"
    return f"~ {m + '.' if m else ''}{w}: {c.get('old')} -> {c.get('new')}"
