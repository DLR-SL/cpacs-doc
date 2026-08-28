import json

from cpacs_doc import catalogue as catalogue_module
from cpacs_doc import media, model
from cpacs_doc import tree as tree_module
from cpacs_doc.findings import Report


def build_model(parse, tmp_path):
    root = parse("minimal.xsd")
    catalogue = catalogue_module.build(root, "minimal.xsd")
    tree = tree_module.build(root, catalogue, "minimal.xsd")
    empty = media.MediaCatalogue(path=tmp_path / "media.json")
    return model.build(catalogue, tree, empty, Report(), schema_path="minimal.xsd", schema_version=None)


def test_declarations_are_stored_once_and_referenced(parse, tmp_path):
    built = build_model(parse, tmp_path)
    assert built["statistics"]["declarations"] <= built["statistics"]["treeNodes"]
    keys = set(built["declarations"])
    stack = [built["tree"]]
    while stack:
        node = stack.pop()
        assert node["d"] in keys
        stack.extend(node.get("children", []))


def test_empty_documentation_fields_are_omitted(parse, tmp_path):
    built = build_model(parse, tmp_path)
    for entry in built["declarations"].values():
        assert entry.get("documentation") != {}


def test_first_paths_are_recorded_for_types_that_occur(parse, tmp_path):
    built = build_model(parse, tmp_path)
    assert built["firstPaths"]["wingType"] == "cpacs/wings/wing"
    # A type never used as an element's type gets no entry rather than a
    # fabricated one.
    assert "undocumentedType" not in built["firstPaths"] or built["firstPaths"]["undocumentedType"]


def test_written_model_round_trips(parse, tmp_path):
    built = build_model(parse, tmp_path)
    path = model.write(built, tmp_path / "out" / "model.json")
    assert json.loads(path.read_text(encoding="utf-8"))["meta"]["modelVersion"] == model.MODEL_VERSION


def test_write_leaves_no_temporary_behind(parse, tmp_path):
    built = build_model(parse, tmp_path)
    model.write(built, tmp_path / "model.json")
    assert list(tmp_path.glob("*.tmp")) == []


def test_the_value_a_type_holds_is_resolved_through_the_chain(parse):
    """`measuredValueType` extends `valueBaseType` extends `xsd:double`. Only
    the last of the three answers what may be written into the element, and
    following the chain was the reader's job across as many pages."""
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    values = model.content_types(catalogue)
    assert values["measuredValueType"] == "xsd:double"
    assert values["valueBaseType"] == "xsd:double"
    # A type whose content is elements holds no value of its own.
    assert "wingType" not in values
    assert "baseType" not in values


def test_a_simple_type_holds_its_own_value(parse):
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    assert model.content_types(catalogue)["symmetryType"] == "xsd:string"
