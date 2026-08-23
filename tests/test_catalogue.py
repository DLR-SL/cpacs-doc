from cpacs_doc import catalogue as catalogue_module


def test_named_types_are_catalogued(parse):
    catalogue = catalogue_module.build(parse("minimal.xsd"), "minimal.xsd")
    assert set(catalogue.types) >= {"baseType", "wingType", "undocumentedType", "outlierType"}


def test_derivation_and_compositor_are_read_through_the_extension(parse):
    catalogue = catalogue_module.build(parse("minimal.xsd"), "minimal.xsd")
    wing = catalogue.get("wingType")
    assert (wing.base, wing.derivation, wing.compositor) == ("baseType", "extension", "sequence")


def test_undocumented_types_are_listed(parse):
    catalogue = catalogue_module.build(parse("minimal.xsd"), "minimal.xsd")
    assert "undocumentedType" in {t.name for t in catalogue.undocumented}
    assert catalogue.get("wingType").documented


def test_content_wrapper_is_reported_not_reinterpreted(parse):
    catalogue = catalogue_module.build(parse("minimal.xsd"), "minimal.xsd")
    codes = {f.code for f in catalogue.findings}
    assert "SCHEMADOC_UNEXPECTED_CHILD" in codes
    # The body is not recovered from the wrapper: reporting is the behaviour.
    assert catalogue.get("outlierType").doc.remarks is None


def test_inline_type_is_folded_into_its_element(parse):
    catalogue = catalogue_module.build(parse("minimal.xsd"), "minimal.xsd")
    assert not any(f.code == "TYPE_SYNTHETIC_NAME_COLLISION" for f in catalogue.findings)
