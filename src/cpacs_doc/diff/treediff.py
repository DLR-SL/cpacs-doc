"""Merge the instance trees of two cpacs-doc models into one diff tree.

Every node carries a status: ``same``, ``add``, ``del``, ``mod`` (type or
cardinality changed) or ``doc`` (only documentation changed). Unchanged
subtrees are cut and only counted (``h``), so the viewer can show them
collapsed next to the changes.

Node keys are short because the tree is embedded in the HTML:
``n`` name, ``t`` type, ``o`` occurrence, ``s`` status, ``k`` children,
``d`` documentation, ``ot``/``oo``/``od`` the old type/occurrence/documentation,
``ren`` the name on the other side of a (suspected or confirmed) rename (the
new node then holds the diff against the old one, which stays as a stub),
``rc`` true if the rename is confirmed, ``why`` the reason for the pairing, ``c`` number of changed children,
``h`` number of hidden unchanged descendants, ``at`` changed attributes, ``mv`` the old path of a moved
node (``mvn`` its old name if that differs), and on the stub left at the old
place (status ``mvd``) ``mvTo`` its new path.
"""
from __future__ import annotations

import difflib

GENERIC_TYPES = {"stringBaseType", "doubleBaseType", "stringUIDBaseType", "integerBaseType", "booleanBaseType"}


ATTR_FIELDS = ("type", "use", "default", "fixed")


def _attributes(types: dict, type_name: str | None) -> dict:
    t = types.get(type_name) if type_name else None
    out = {}
    for a in (t or {}).get("attributes", []):
        doc = a.get("documentation") or {}
        out[a["name"]] = {f: a.get(f) for f in ATTR_FIELDS} | {"doc": doc.get("text") or doc.get("summary") or ""}
    return out


def _groups(types: dict, type_name: str | None) -> tuple[dict, dict]:
    """The compositor groups of a type: ``{group path: compositor}`` and ``{element name: group
    path}``. A path is the index of the top-level group, then the member index of each nested
    group, joined by dots ("0", "0.4")."""
    comps: dict[str, str] = {}
    where: dict[str, str] = {}

    def walk(members, path):
        for i, m in enumerate(members):
            if m.get("kind") == "group":
                walk_group(m, f"{path}.{i}")
            elif m.get("kind") == "element":
                where.setdefault(m["name"], path)

    def walk_group(g, path):
        comps[path] = g.get("compositor") or "sequence"
        walk(g.get("members", []), path)

    t = types.get(type_name) if type_name else None
    for i, g in enumerate((t or {}).get("children", [])):
        if g.get("kind") == "group":
            walk_group(g, str(i))
        elif g.get("kind") == "element":
            comps.setdefault("0", "sequence")
            where.setdefault(g["name"], "0")
    return comps, where


def _tree(model: dict) -> dict:
    decl = model["declarations"]
    types = model.get("types", {})
    cache: dict = {}

    def conv(n):
        d = decl[n["d"]]
        doc = d.get("documentation") or {}
        t = d.get("type")
        if t not in cache:
            cache[t] = (_attributes(types, t), *_groups(types, t))
        attrs, comps, where = cache[t]
        return {"name": d["name"], "type": t, "min": d.get("minOccurs"), "max": d.get("maxOccurs"),
                "doc": doc.get("text") or doc.get("summary") or "", "attrs": attrs,
                "comps": comps, "where": where,
                "kids": [conv(c) for c in n.get("children", [])]}

    return conv(model["tree"])


def attribute_changes(old: dict, new: dict) -> list[dict]:
    """Changed attributes of one node: ``n`` name, ``s`` add/del/mod/doc, old values as ``o*``."""
    out = []
    for name in sorted(old.keys() | new.keys()):
        a, b = old.get(name), new.get(name)
        if a is None:
            out.append({"n": name, "s": "add", "t": b["type"], "u": b["use"] or "optional"})
        elif b is None:
            out.append({"n": name, "s": "del", "t": a["type"], "u": a["use"] or "optional"})
        else:
            ch = {"n": name, "t": b["type"], "u": b["use"] or "optional"}
            for f, key in (("type", "ot"), ("use", "ou"), ("default", "od"), ("fixed", "of")):
                if a[f] != b[f]:
                    ch[key] = a[f] if f != "use" else (a[f] or "optional")
            if len(ch) > 3:
                out.append(ch | {"s": "mod"})
            elif a["doc"] != b["doc"]:
                out.append(ch | {"s": "doc"})
    return out


def occ(x: dict) -> str:
    lo = 1 if x["min"] is None else x["min"]
    hi = x["max"]
    hi = 1 if hi is None else ("∞" if hi in ("unbounded", -1) else hi)
    return f"{lo}..{hi}"


def _count(n: dict) -> int:
    return 1 + sum(_count(c) for c in n["kids"])


def _node(x, status, old=None, doc_len=400):
    r = {"n": x["name"], "t": x["type"], "o": occ(x), "s": status, "k": []}
    if x["doc"]:
        r["d"] = x["doc"][:doc_len]
    if old is not None:
        if old["type"] != x["type"]:
            r["ot"] = old["type"]
        if occ(old) != occ(x):
            r["oo"] = occ(old)
        if old["doc"] != x["doc"]:
            r["od"] = old["doc"][:doc_len]
        at = attribute_changes(old.get("attrs", {}), x.get("attrs", {}))
        if at:
            r["at"] = at
    return r


def _set_groups(r: dict, new: dict | None, old: dict | None) -> None:
    """Compositors of r's content (``gc``, old ones that differ in ``gco``) and the group
    of each child (``gp``): from the new type, for removed children from the old one."""
    nc = (new or {}).get("comps", {})
    oc = (old or {}).get("comps", {})
    if not (nc or oc):
        return
    gc = dict(nc)
    # A top-level group is the same group on both sides; a changed compositor there is shown on it.
    changed = {p: c for p, c in oc.items() if "." not in p and p in nc and nc[p] != c}
    if changed:
        r["gco"] = changed
    nw, ow = (new or {}).get("where", {}), (old or {}).get("where", {})

    def old_group(path: str) -> str:
        # Follow the old path as long as the new type has the same groups; from the first
        # nested group that differs on, the removed node sits in an old group of its own ("~o").
        parts = path.split(".")
        key, real = parts[0], parts[0]
        if key not in gc:
            gc[key] = oc.get(key, "sequence")
        diverged = False
        for seg in parts[1:]:
            real = f"{real}.{seg}"
            if not diverged and nc.get(real) == oc.get(real):
                key = real
            else:
                diverged = True
                key = f"{key}.{seg}~o"
                gc[key] = oc.get(real, "sequence")
        return key

    for k in r["k"]:
        if k["s"] not in ("del", "mvd") and k["n"] in nw:
            k["gp"] = nw[k["n"]]
        elif k["n"] in ow:
            k["gp"] = old_group(ow[k["n"]])
        else:
            k["gp"] = nw.get(k["n"], "0")
    r["gc"] = gc


def _whole(x, status):
    r = _node(x, status)
    r["k"] = [_whole(c, status) for c in x["kids"]]
    _set_groups(r, x, None)
    r["_raw"] = x          # kept until move detection is done, then removed
    return r


def _child_names(n: dict) -> set[str]:
    return {k["n"] for k in n["k"]}


def _pair_renames(kids: list[dict], parent_type: str | None, decisions) -> None:
    """Pair removed and added siblings. A confirmed decision wins, a rejected pair is never
    guessed; otherwise same specific type, similar name or mostly the same children."""
    dels = [k for k in kids if k["s"] == "del"]
    adds = [k for k in kids if k["s"] == "add"]
    for d in dels:
        hit, why = None, ""
        target = decisions.target(parent_type, d["n"]) if decisions else None
        for a in adds:
            if "ren" in a:
                continue
            if target is not None:
                if a["n"] == target:
                    hit, why = a, "confirmed"
                    break
                continue
            if decisions and decisions.rejected(parent_type, d["n"], a["n"]):
                continue
            if d["t"] == a["t"] and d["t"] not in GENERIC_TYPES:
                hit, why = a, "same type"
                break
            if difflib.SequenceMatcher(None, d["n"].lower(), a["n"].lower()).ratio() >= 0.85:
                hit, why = a, "similar name"
                break
            cd, ca = _child_names(d), _child_names(a)
            if len(cd) >= 2 and len(cd & ca) / len(cd | ca) >= 0.6:
                hit, why = a, f"{len(cd & ca)} of {len(cd | ca)} children shared"
                break
        if hit:
            hit["ren"], d["ren"] = d["n"], hit["n"]
            hit["why"] = d["why"] = why
            if target is not None:
                hit["rc"] = d["rc"] = True


def merge(old_model: dict, new_model: dict, decisions=None) -> dict:
    """``decisions``: a :class:`renames.Decisions` or None (heuristics only)."""

    def merge_node(a, b):
        if a is None:
            return _whole(b, "add")
        if b is None:
            return _whole(a, "del")
        r = _node(b, "same", a)
        if "ot" in r or "oo" in r or any(x["s"] != "doc" for x in r.get("at", [])):
            r["s"] = "mod"
        elif "od" in r or r.get("at"):
            r["s"] = "doc"
        ka = {c["name"]: c for c in a["kids"]}
        kb = {c["name"]: c for c in b["kids"]}
        order = [c["name"] for c in b["kids"]] + [n for n in ka if n not in kb]
        kids = [merge_node(ka.get(n), kb.get(n)) for n in order]
        _pair_renames(kids, b["type"], decisions)
        # A renamed node is compared with its old self: the new one carries the
        # diff of both subtrees, the old one stays as a stub next to it.
        by_name = {k["n"]: k for k in kids}
        for i, k in enumerate(kids):
            if k["s"] == "add" and "ren" in k and "_raw" in k:
                old_k = by_name[k["ren"]]
                merged = merge_node(old_k["_raw"], k["_raw"])
                for f in ("ren", "why", "rc"):
                    if f in k:
                        merged[f] = k[f]
                kids[i] = merged
                old_k["h"] = _count(old_k["_raw"]) - 1
                old_k["k"] = []
        r["k"] = kids
        _set_groups(r, b, a)
        r["c"] = sum(1 for k in kids if k["s"] != "same" or k.get("c"))
        if not r["c"]:
            r["k"] = []
            r["h"] = _count(b) - 1
        return r

    def drop_raw(r):
        r.pop("_raw", None)
        for k in r["k"]:
            drop_raw(k)

    def prune(r):
        if r["s"] in ("add", "del"):
            return r
        r["k"] = [({k2: v for k2, v in k.items() if k2 != "k"} | {"k": []})
                  if k["s"] == "same" and not k.get("c") else prune(k) for k in r["k"]]
        return r

    tree = merge_node(_tree(old_model), _tree(new_model))
    _detect_moves(tree, merge_node, decisions)
    drop_raw(tree)
    return prune(tree)


def _walk_with_parents(n, parent, path, depth, out):
    path = path + [n["n"]]
    out.append((n, parent, path, depth))
    for k in n["k"]:
        _walk_with_parents(k, n, path, depth + 1, out)


def _descendant_ids(n, into: set) -> None:
    into.add(id(n))
    for k in n["k"]:
        _descendant_ids(k, into)


def _common_prefix(a: list, b: list) -> int:
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


def _detect_moves(tree: dict, merge_node, decisions) -> None:
    """Pair a removed node at one place with an added node at another.

    A pair needs the same name (or a confirmed rename of it) and either the same
    specific type or mostly the same children; only nodes with content count, a
    lone ``name`` or ``uID`` moving is noise. Removed nodes are taken top-down, so
    a moved subtree is paired at its top. Among several candidates the one whose
    place shares most of the old path wins (aircraft stays with aircraft).

    The added node is replaced by the diff of the old and the new subtree, with
    ``mv`` naming where it came from; the removed node becomes a stub with status
    ``mvd`` and ``mvTo`` naming where it went.
    """
    nodes: list = []
    _walk_with_parents(tree, None, [], 0, nodes)
    dels = [x for x in nodes if x[0]["s"] == "del" and "ren" not in x[0] and x[0]["k"]]
    adds = [x for x in nodes if x[0]["s"] == "add" and "ren" not in x[0] and x[0]["k"]]
    if not dels or not adds:
        return
    by_name: dict[str, list] = {}
    for x in adds:
        by_name.setdefault(x[0]["n"], []).append(x)
    used: set = set()
    dels.sort(key=lambda x: x[3])
    for d, dparent, dpath, _ in dels:
        if id(d) in used:
            continue
        names = {d["n"]}
        if decisions:
            t = decisions.target(None, d["n"])
            if t:
                names.add(t)
        best, best_key = None, None
        for name in names:
            for a, aparent, apath, _ in by_name.get(name, []):
                if id(a) in used:
                    continue
                if d["t"] == a["t"] and d["t"] not in GENERIC_TYPES:
                    score = 2
                else:
                    cd, ca = _child_names(d), _child_names(a)
                    if len(cd) >= 2 and len(cd & ca) / len(cd | ca) >= 0.6:
                        score = 1
                    else:
                        continue
                key = (score, _common_prefix(dpath, apath))
                if best_key is None or key > best_key:
                    best, best_key = (a, aparent, apath), key
        if best is None:
            continue
        a, aparent, apath = best
        _descendant_ids(d, used)
        _descendant_ids(a, used)
        moved = merge_node(d["_raw"], a["_raw"])
        moved["mv"] = "/" + "/".join(dpath)
        if d["n"] != a["n"]:
            moved["mvn"] = d["n"]
        if "gp" in a:
            moved["gp"] = a["gp"]
        aparent["k"][aparent["k"].index(a)] = moved
        stub = {"n": d["n"], "t": d["t"], "o": d["o"], "s": "mvd", "k": [],
                "mvTo": "/" + "/".join(apath), "h": _count(d["_raw"]) - 1}
        if "gp" in d:
            stub["gp"] = d["gp"]
        dparent["k"][dparent["k"].index(d)] = stub


def hotspots(tree: dict) -> list[dict]:
    """Places with changed children, grouped by the type that holds them."""
    hot: dict[str, dict] = {}

    def walk(n, path):
        path = f"{path}/{n['n']}"
        a = sum(1 for k in n["k"] if k["s"] == "add")
        d = sum(1 for k in n["k"] if k["s"] in ("del", "mvd"))
        m = sum(1 for k in n["k"] if k["s"] in ("mod", "doc") or "mv" in k or ("ren" in k and k["s"] != "del"))
        if n["s"] not in ("add", "del") and (a or d or m):
            key = n["t"] or n["n"]
            h = hot.setdefault(key, {"t": key, "a": a, "d": d, "m": m, "paths": []})
            h["paths"].append(path)
        for k in n["k"]:
            walk(k, path)

    walk(tree, "")
    return sorted(hot.values(), key=lambda h: -(h["a"] + h["d"] + h["m"]))


def path_stats(tree: dict) -> dict:
    s = {"add": 0, "del": 0, "mod": 0, "doc": 0, "renames": 0, "moves": 0}

    def walk(n):
        if n["s"] in s:
            s[n["s"]] += 1
        if "mv" in n:
            s["moves"] += 1
        if n["s"] != "del" and "ren" in n:
            s["renames"] += 1
        for k in n["k"]:
            walk(k)

    walk(tree)
    return s
