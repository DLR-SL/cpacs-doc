from cpacs_doc import catalogue as catalogue_module
from cpacs_doc import content


def read(parse, type_name):
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    return content.read(catalogue.get(type_name), catalogue, "content.xsd")


def test_inherited_attributes_are_included_and_marked(parse):
    """1,080 of 1,101 CPACS types derive, and 300 of 311 attribute
    declarations sit on an extension rather than on the type itself."""
    result = read(parse, "wingType")
    names = {a.name: a for a in result.attributes}
    assert names["uID"].inherited is False
    assert names["externalFileName"].inherited is True
    assert names["externalFileName"].declared_in == "baseType"


def test_use_defaults_to_optional(parse):
    names = {a.name: a for a in read(parse, "wingType").attributes}
    assert names["symmetry"].use == "optional"
    assert names["uID"].use == "required"


def test_default_and_fixed_are_kept(parse):
    names = {a.name: a for a in read(parse, "wingType").attributes}
    assert names["symmetry"].default == "none"


def test_a_restricted_attribute_keeps_the_nearest_declaration(parse):
    """A derived type may narrow an inherited attribute; the type's own
    declaration is the one an instance sees."""
    names = {a.name: a for a in read(parse, "wingType").attributes}
    assert names["externalDataDirectory"].use == "required"
    assert names["externalDataDirectory"].inherited is False


def test_enumeration_values_belong_to_their_own_type(parse):
    """Descending freely would attribute a child's inline enumeration to the
    parent, and count it twice overall."""
    parent = read(parse, "wingType")
    assert parent.enumeration == []
    values = [v.value for v in read(parse, "symmetryType").enumeration]
    assert values == ["none", "x-y-plane", "x-z-plane"]


def test_enumeration_documentation_is_read(parse):
    values = {v.value: v for v in read(parse, "symmetryType").enumeration}
    assert "no symmetry" in values["none"].doc.text


def test_children_include_inherited_content(parse):
    names = [c.name for c in read(parse, "wingType").children]
    assert "uID" not in names
    assert names[:2] == ["baseField", "span"]


def test_child_cardinality_and_compositor(parse):
    children = {c.name: c for c in read(parse, "wingType").children}
    assert children["span"].min_occurs == 1
    assert children["segment"].max_occurs is None
    assert children["segment"].compositor == "sequence"


def test_type_without_content_is_empty(parse):
    assert read(parse, "emptyType").is_empty
