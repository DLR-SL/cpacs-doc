"""cpacs-doc diff on two small schemas that hold one change of each kind."""
from pathlib import Path

import pytest

from cpacs_doc import cli
from cpacs_doc.diff import renames, run, treediff, typediff

FIX = Path(__file__).parent / "fixtures" / "diff"


@pytest.fixture(scope="module")
def pair():
    return run.build_model(FIX / "old.xsd"), run.build_model(FIX / "new.xsd")


def node(tree, path):
    n = tree
    for part in path.split("/")[1:]:
        n = next(k for k in n["k"] if k["n"] == part)
    return n


def test_types(pair):
    d = typediff.diff_types(*pair)
    assert d["removed"] == ["alphaType", "betaType", "holderType", "legacyType"]
    assert d["added"] == ["alphaBetaType", "containerType"]
    whats = {(c["what"], c.get("member")) for c in d["changed"]["caseType"]}
    assert ("added", "el:referencePoint") in whats
    assert ("removed", "el:refPoint") in whats
    assert ("type", "el:mass") in whats
    assert ("documentation", "el:note") in whats


def test_tree_status(pair):
    t = treediff.merge(*pair)
    assert node(t, "/fresh")["s"] == "add"
    assert node(t, "/legacy")["s"] == "del"
    assert node(t, "/caseB")["oo"] == "0..1" and node(t, "/caseB")["s"] == "mod"
    mass = node(t, "/caseA/mass")
    assert (mass["s"], mass["ot"], mass["t"]) == ("mod", "xsd:string", "xsd:double")
    assert node(t, "/caseA/note")["s"] == "doc"


def test_rename_guess_and_confirmation(pair):
    t = treediff.merge(*pair)
    ref = node(t, "/caseA/referencePoint")
    assert ref["ren"] == "refPoint" and "rc" not in ref
    d = renames.Decisions()
    d.set_confirm("refPoint", "referencePoint")
    t = treediff.merge(*pair, d)
    assert node(t, "/caseA/referencePoint")["rc"] is True
    d = renames.Decisions()
    d.set_reject("refPoint", "referencePoint")
    t = treediff.merge(*pair, d)
    assert "ren" not in node(t, "/caseA/referencePoint")


def test_decisions_round_trip(tmp_path):
    d = renames.Decisions()
    d.set_confirm("refPoint", "referencePoint")
    d.set_confirm("a", "b", "someType")
    d.set_reject("settings", "setting")
    f = tmp_path / "x.renames.toml"
    renames.save(d, f)
    back = renames.load([f.read_text(encoding="utf-8")])
    assert back.confirm == d.confirm and back.reject == d.reject


def test_move_is_paired_and_diffed_inside(pair):
    d = renames.Decisions()
    d.set_confirm("storage", "reservoirs")
    t = treediff.merge(*pair, d)
    stub = node(t, "/holder/fuel")
    assert stub["s"] == "mvd" and stub["mvTo"] == "/cpacs/container/fuel" and stub["k"] == []
    moved = node(t, "/container/fuel")
    assert moved["mv"] == "/cpacs/holder/fuel" and moved["s"] == "same"
    assert node(t, "/container/fuel/extra")["s"] == "add"
    reservoirs = node(t, "/container/fuel/reservoirs")
    assert reservoirs["ren"] == "storage" and reservoirs["rc"] is True and reservoirs["s"] == "doc"
    assert node(t, "/container/label")["s"] == "add"
    assert treediff.path_stats(t)["moves"] == 1


def test_renamed_node_holds_the_diff_and_leaves_a_stub(pair):
    t = treediff.merge(*pair)
    old = node(t, "/caseA/refPoint")
    assert old["s"] == "del" and old["k"] == [] and old["h"] == 3
    assert node(t, "/caseA/referencePoint")["s"] == "same"


def test_compatibility_classes(pair):
    from cpacs_doc.diff import compat
    d = renames.Decisions()
    d.set_confirm("storage", "reservoirs")
    t = treediff.merge(*pair, d)
    counts = compat.annotate(t, typediff.diff_types(*pair))
    assert node(t, "/legacy")["cx"] == "break"
    assert "value" not in [k["n"] for k in node(t, "/legacy")["k"] if "cx" in k]   # only the top counts
    assert node(t, "/caseB")["cx"] == "break" and "now required" in node(t, "/caseB")["cr"][0]
    assert node(t, "/caseA/mass")["cx"] == "review"
    assert node(t, "/fresh")["cx"] == "ok"
    assert node(t, "/container")["cx"] == "ok" and "cx" not in node(t, "/container/label")
    moved = node(t, "/container/fuel")
    assert moved["cx"] == "break" and moved["mg"] is True
    assert node(t, "/caseA/referencePoint")["mg"] is True
    assert node(t, "/caseA/note")["cx"] == "ok"
    assert t["cxs"] == "break"
    assert counts["migratable"] >= 3


def test_enumeration_and_compositor_reasons():
    from cpacs_doc.diff import compat
    r = compat.type_reasons([
        {"what": "facet", "member": "enumeration", "old": [{"value": "a"}, {"value": "b"}], "new": [{"value": "a"}, {"value": "c"}]},
        {"what": "compositor", "old": "all", "new": "sequence"},
    ])
    assert ("break", "enumeration values removed: b") in r
    assert ("ok", "enumeration values added: c") in r
    assert r[-1][0] == "break" and "order" in r[-1][1]


def test_attribute_changes(pair):
    from cpacs_doc.diff import compat
    t = treediff.merge(*pair)
    compat.annotate(t, typediff.diff_types(*pair))
    case = node(t, "/caseA")
    at = {a["n"]: a for a in case["at"]}
    assert at["flag"]["s"] == "add" and at["legacyAttr"]["s"] == "del"
    assert at["uID"]["s"] == "mod" and at["uID"]["ou"] == "optional" and at["uID"]["u"] == "required"
    assert case["s"] == "mod" and case["cx"] == "break"
    assert any("@uID now required" in r for r in case["cr"])
    assert any("@legacyAttr removed" in r for r in case["cr"])


def test_merged_types(pair):
    from cpacs_doc.diff import typemap
    t = treediff.merge(*pair)
    tm = typemap.type_map(t, typediff.diff_types(*pair), pair[0]["types"], pair[1]["types"])
    merged = [e for e in tm if e["kind"] == "merged"]
    assert merged and merged[0]["old"] == ["alphaType", "betaType"] and merged[0]["new"] == ["alphaBetaType"]
    assert typemap.note_for(merged[0]).startswith("types merged: alphaType, betaType")


def test_choices_in_compatibility(pair):
    from cpacs_doc.diff import compat
    t = treediff.merge(*pair)
    compat.annotate(t, typediff.diff_types(*pair))
    pz = node(t, "/caseA/referencePoint/pz")
    assert pz["s"] == "add" and pz["cx"] == "ok" and "existing choice" in pz["cr"][0]
    ca = node(t, "/container/fuel/reservoirs/ca")
    assert ca["s"] == "add" and ca["cx"] == "break" and "new required choice" in ca["cr"][0]


def test_renames_subset_parser_matches_tomllib():
    d = renames.Decisions()
    d.set_confirm("refPoint", "referencePoint")
    d.set_confirm("a", "b", "someType")
    d.set_reject('q"uote', "x")
    text = renames.dump(d)
    tomllib = pytest.importorskip("tomllib")
    assert renames._loads_subset(text) == {k: tomllib.loads(text).get(k, []) for k in ("rename", "reject")}



def test_cli_writes_the_four_files(tmp_path, capsys):
    (tmp_path / "new").mkdir()
    new = tmp_path / "new" / "cpacs_schema.xsd"
    new.write_text((FIX / "new.xsd").read_text())
    (tmp_path / "new" / "cpacs_schema.renames.toml").write_text(
        '[[rename]]\nold = "refPoint"\nnew = "referencePoint"\n')
    out = tmp_path / "out"
    assert cli.main(["diff", str(FIX / "old.xsd"), str(new), "-o", str(out), "--link", "https://example.org/d"]) == 0
    assert {p.name for p in out.iterdir()} == {"diff.html", "report.md", "summary.md", "diff.json"}
    html = (out / "diff.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "window.DIFF=" in html and "/*DATA*/" not in html
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "[Open the diagram](https://example.org/d)" in summary and "types merged" in summary
    assert "`refPoint` → `referencePoint`\n" in (out / "report.md").read_text(encoding="utf-8")
    assert "breaking" in capsys.readouterr().out


def test_cli_diff_missing_file(tmp_path):
    assert cli.main(["diff", str(tmp_path / "nope.xsd"), str(FIX / "new.xsd")]) == 2
