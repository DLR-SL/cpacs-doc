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


def flatten(members):
    """Element members in document order, groups walked through."""
    out = []
    for member in members:
        if hasattr(member, "compositor"):
            out.extend(flatten(member.members))
        else:
            out.append(member)
    return out


def test_children_include_inherited_content(parse):
    """1,080 of 1,101 CPACS types derive, and the base type's content comes
    first in an instance."""
    names = [c.name for c in flatten(read(parse, "wingType").children)]
    assert "uID" not in names
    assert names[:2] == ["baseField", "span"]


def test_children_are_grouped_by_compositor(parse):
    """A compositor governs a set of children; 84 choice groups in the schema
    decide between alternatives, and ten types contain more than one."""
    groups = read(parse, "wingType").children
    assert [g.compositor for g in groups] == ["sequence", "sequence"]


def test_child_cardinality_is_read(parse):
    children = {c.name: c for c in flatten(read(parse, "wingType").children)}
    assert children["span"].min_occurs == 1
    assert children["segment"].max_occurs is None


def test_nested_groups_are_preserved(parse):
    """48 of the 84 choice groups decide between groups of elements rather
    than between single ones."""
    outer = read(parse, "choiceType").children[0]
    assert outer.compositor == "sequence"
    inner = [m for m in outer.members if hasattr(m, "compositor")]
    assert [g.compositor for g in inner] == ["choice"]
    assert inner[0].min_occurs == 0
    alternatives = inner[0].members
    assert alternatives[0].name == "either"
    assert [m.name for m in alternatives[1].members] == ["bothA", "bothB"]


def test_type_without_content_is_empty(parse):
    assert read(parse, "emptyType").is_empty


def test_a_child_naming_no_type_names_the_one_it_declares(parse):
    """An element may declare its type on the spot. Unless the child says which
    catalogue entry that is, everything the type holds — in CPACS 3.5.1 that is
    187 of the 265 enumeration values — is unreachable from the page that needs
    it: the entry exists, and nothing points at it.
    """
    children = {c.name: c for c in flatten(read(parse, "wingType").children)}
    assert children["mode"].type_name == "wingType/mode"
    # a child that names a type still names that one
    assert children["span"].type_name == "xsd:double"


def test_an_attribute_naming_no_type_names_the_one_it_declares(parse):
    """The base alone would say `xsd:string` and lose the two allowed values."""
    names = {a.name: a for a in read(parse, "wingType").attributes}
    assert names["rating"].type_name == "wingType/rating"
    assert names["symmetry"].type_name == "symmetryType"


def test_the_declared_type_holds_the_values(parse):
    """The other half of the reference: what it points at is the thing that
    knows, and it is catalogued under exactly that name."""
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    for name, expected in (("wingType/mode", ["inline-only"]),
                           ("wingType/rating", ["draft", "final"])):
        entry = catalogue.get(name)
        assert entry is not None and entry.anonymous
        values = content.read(entry, catalogue, "content.xsd").enumeration
        assert [v.value for v in values] == expected


def test_facets_are_read_and_kept_apart_from_the_values(parse):
    """An enumeration says which values there are; a facet says what a value
    must satisfy. Reading only the first left 30 constraints in the schema —
    every pattern and every bound — out of the documentation entirely."""
    root = parse("content.xsd")
    catalogue = catalogue_module.build(root, "content.xsd")
    ratio = content.read(catalogue.get("wingType/ratio"), catalogue, "content.xsd")
    assert [(f.name, f.value) for f in ratio.facets] == [
        ("minInclusive", "0"), ("maxInclusive", "1"),
    ]
    assert ratio.enumeration == []
    # and the other way round
    symmetry = read(parse, "symmetryType")
    assert symmetry.facets == []
    assert len(symmetry.enumeration) == 3


def test_facets_belong_to_their_own_type(parse):
    """As with the values: a free descent would take a child's constraints and
    attribute them to the parent."""
    assert read(parse, "wingType").facets == []


def test_a_declared_default_and_a_fixed_value_are_read_and_kept_apart(parse):
    """Twelve elements in CPACS 3.5.1 carry a default and the predecessor never
    wrote one out, so a reader who cannot open the schema cannot learn that
    `controlPointNumber` means 12 when it is left out.

    Default and fixed are two different statements — one is what an instance
    means by omitting the element, the other the only value it may write — so
    they stay two fields.
    """
    children = {c.name: c for c in flatten(read(parse, "wingType").children)}
    assert children["ratio"].default == "0.5" and children["ratio"].fixed is None
    assert children["unit"].fixed == "m" and children["unit"].default is None
    assert children["span"].default is None and children["span"].fixed is None
