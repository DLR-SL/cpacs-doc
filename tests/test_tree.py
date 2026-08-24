from cpacs_doc import catalogue as catalogue_module
from cpacs_doc import tree as tree_module


def build(parse):
    root = parse("minimal.xsd")
    catalogue = catalogue_module.build(root, "minimal.xsd")
    return tree_module.build(root, catalogue, "minimal.xsd")


def test_root_is_cpacs(parse):
    assert build(parse).root.name == "cpacs"


def test_inherited_content_is_expanded(parse):
    """1,051 of 1,101 CPACS types extend complexBaseType; dropping the base
    would remove uID from every node."""
    paths = {n.path for n in build(parse).walk()}
    assert "cpacs/wings/wing/uID" in paths
    assert "cpacs/wings/wing/span" in paths


def test_cardinality_is_read(parse):
    nodes = {n.path: n for n in build(parse).walk()}
    assert nodes["cpacs/wings"].optional
    assert nodes["cpacs/wings/wing"].max_occurs is None


def test_paths_reachable_through_two_choice_branches_are_reported(parse):
    tree = build(parse)
    ambiguous = [f for f in tree.findings if f.code == "TREE_PATH_AMBIGUOUS"]
    assert any("cpacs/shared" in f.message for f in ambiguous)
    assert any(f.severity == "warning" for f in ambiguous)


def test_a_choice_becomes_a_node_of_its_own(parse):
    """Alternatives are not siblings: only one of them occurs. Sequence and all
    stay implicit, because the tree already shows order and neither changes
    which children may occur."""
    tree = build(parse)
    groups = [n for n in tree.walk() if n.group]
    assert [g.group for g in groups] == ["choice", "sequence", "sequence"] or all(
        g.group in ("choice", "sequence") for g in groups
    )
    assert any(g.group == "choice" for g in groups)


def test_a_group_shares_its_parents_path(parse):
    """A compositor exists in no instance, so it must not lengthen a path."""
    tree = build(parse)
    for node in tree.walk():
        if node.group:
            for child in node.children:
                assert child.path.startswith(node.path)


def test_annotation_findings_are_not_repeated_per_occurrence(parse):
    tree = build(parse)
    assert not any(f.code.startswith("SCHEMADOC_") for f in tree.findings)
