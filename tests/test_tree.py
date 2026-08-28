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


def test_choice_members_are_marked_not_nested(parse):
    """The tree stays flat: indentation there means containment in an instance,
    and a compositor contains nothing. The constraint rides on the node."""
    tree = build(parse)
    marked = {n.name for n in tree.walk() if n.alternative}
    assert marked == {"shared", "either", "bothA", "bothB"}
    depths = {n.name: n.depth for n in tree.walk() if n.name in marked | {"odd"}}
    assert depths["either"] == depths["bothA"] == depths["odd"]


def test_alternatives_are_counted(parse):
    """`shared` appears in both branches of the first choice, so it counts
    twice; `either`, `bothA` and `bothB` once each."""
    assert build(parse).alternatives == 5


def test_annotation_findings_are_not_repeated_per_occurrence(parse):
    tree = build(parse)
    assert not any(f.code.startswith("SCHEMADOC_") for f in tree.findings)


def test_a_node_whose_type_is_declared_inline_names_it(parse):
    """The viewer shows a node's type and everything that type says. With no
    type on the declaration it showed neither, though the entry was there."""
    def find(node, name):
        if node.name == name:
            return node
        for child in node.children:
            hit = find(child, name)
            if hit is not None:
                return hit
        return None

    # content.xsd is the fixture with an element that declares its own type.
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    tree = tree_module.build(root, catalogue, "content.xsd")
    mode = find(tree.root, "mode")
    assert mode is not None
    assert mode.type_name == "wingType/mode"


def test_a_node_carries_the_default_of_its_declaration(parse):
    """The panel says what the element is worth unwritten, and it can only say
    it if the declaration brought it along."""
    def find(node, name):
        if node.name == name:
            return node
        for child in node.children:
            hit = find(child, name)
            if hit is not None:
                return hit
        return None

    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    tree = tree_module.build(root, catalogue, "content.xsd")
    assert find(tree.root, "ratio").default == "0.5"
    assert find(tree.root, "unit").fixed == "m"
    assert find(tree.root, "span").default is None
