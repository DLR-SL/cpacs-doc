import json

from cpacs_doc import media


def write(tmp_path, images, **extra):
    payload = {"schemaVersion": 1, "images": images, **extra}
    path = tmp_path / "media.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_alt_is_an_error(tmp_path):
    path = write(tmp_path, {"a": {"file": "a.png"}})
    catalogue = media.load(path)
    assert [f.code for f in catalogue.findings] == ["MEDIA_ENTRY_NO_ALT"]
    assert not catalogue.entries


def test_backslashes_are_rejected(tmp_path):
    path = write(tmp_path, {"a": {"file": "figures\\a.png", "alt": "A"}})
    assert [f.code for f in media.load(path).findings] == ["MEDIA_PATH_NOT_PORTABLE"]


def test_paths_may_not_escape_the_catalogue(tmp_path):
    path = write(tmp_path, {"a": {"file": "../a.png", "alt": "A"}})
    assert [f.code for f in media.load(path).findings] == ["MEDIA_PATH_NOT_CONTAINED"]


def test_unsupported_version_stops_reading(tmp_path):
    path = tmp_path / "media.json"
    path.write_text(json.dumps({"schemaVersion": 99, "images": {}}), encoding="utf-8")
    assert [f.code for f in media.load(path).findings] == ["MEDIA_CATALOGUE_VERSION"]


def test_case_mismatch_is_distinguished_from_absence(tmp_path):
    (tmp_path / "Figure.png").write_bytes(b"")
    path = write(tmp_path, {"a": {"file": "figure.png", "alt": "A"}, "b": {"file": "gone.png", "alt": "B"}})
    catalogue = media.load(path)
    codes = {f.code for f in media.validate(catalogue, {"a", "b"})}
    assert codes == {"MEDIA_FILE_CASE_MISMATCH", "MEDIA_FILE_ABSENT"}


def test_unresolved_and_unreferenced_are_separated(tmp_path):
    (tmp_path / "a.png").write_bytes(b"")
    path = write(tmp_path, {"a": {"file": "a.png", "alt": "A"}})
    findings = media.validate(media.load(path), {"missing"})
    codes = {f.code: f.severity for f in findings}
    assert codes["MEDIA_ID_UNRESOLVED"] == "error"
    assert codes["MEDIA_ENTRY_UNREFERENCED"] == "info"
