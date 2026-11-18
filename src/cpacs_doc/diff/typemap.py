"""Which removed types live on as which added types: renamed, merged or split.

Read from the merged tree: every node present on both sides whose type changed
(``ot`` → ``t``) links an old type to a new one. Only removed and added types count;
a node switching between two types that exist on both sides is an ordinary change.

* renamed – all places of one removed type use one added type, and nothing else does
* merged  – several removed types now use one added type
* split   – the places of one removed type use several added types
"""
from __future__ import annotations

from collections import defaultdict

from .typediff import compare_type


def type_map(tree: dict, types_diff: dict, old_types: dict, new_types: dict) -> list[dict]:
    removed, added = set(types_diff["removed"]), set(types_diff["added"])
    fwd: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    back: dict[str, set[str]] = defaultdict(set)

    def walk(n):
        anonymous = "/" in (n.get("ot") or "") or "/" in (n.get("t") or "")  # follow their parent type
        if (n["s"] not in ("add", "del", "mvd") and not anonymous
                and n.get("ot") in removed and n.get("t") in added):
            fwd[n["ot"]][n["t"]] += 1
            back[n["t"]].add(n["ot"])
        for k in n["k"]:
            walk(k)

    walk(tree)
    out, seen = [], set()
    for new, olds in sorted(back.items()):
        if len(olds) > 1:
            kind = "merged"
        elif len(fwd[next(iter(olds))]) > 1:
            continue  # reported as a split below
        else:
            kind = "renamed"
        olds = sorted(olds)
        entry = {"kind": kind, "old": olds, "new": [new],
                 "places": sum(fwd[o][new] for o in olds),
                 "changes": {o: [c for c in compare_type(old_types[o], new_types[new]) if not _slug_rename(c, o, new)]
                             for o in olds if o in old_types and new in new_types}}
        out.append(entry)
        seen.update(olds)
    for old, news in sorted(fwd.items()):
        if len(news) > 1 and old not in seen:
            out.append({"kind": "split", "old": [old], "new": sorted(news),
                        "places": sum(news.values()),
                        "changes": {}})
    return out


def _slug_rename(c: dict, old: str, new: str) -> bool:
    """An anonymous member type that only follows the rename of its parent type."""
    return (c["what"] == "type" and isinstance(c.get("old"), str) and isinstance(c.get("new"), str)
            and c["old"].startswith(old + "/") and c["new"].startswith(new + "/")
            and c["old"][len(old):] == c["new"][len(new):])


def note_for(entry: dict) -> str:
    if entry["kind"] == "merged":
        return "types merged: " + ", ".join(entry["old"]) + " → " + entry["new"][0]
    if entry["kind"] == "split":
        return "type split: " + entry["old"][0] + " → " + ", ".join(entry["new"])
    return "type renamed: " + entry["old"][0] + " → " + entry["new"][0]
