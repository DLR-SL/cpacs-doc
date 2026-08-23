from pathlib import Path

from cpacs_doc.cli import main

FIXTURE = str(Path(__file__).parent / "fixtures" / "minimal.xsd")


def test_report_without_errors_exits_zero(capsys):
    assert main(["report", FIXTURE, "--no-media"]) == 0
    assert "types:" in capsys.readouterr().out


def test_unresolved_image_without_catalogue_is_only_a_warning(capsys):
    main(["report", FIXTURE, "--no-media"])
    assert "MEDIA_CATALOGUE_NOT_GIVEN" not in capsys.readouterr().out


def test_missing_catalogue_with_references_is_reported(capsys):
    assert main(["report", FIXTURE]) == 0
    assert "MEDIA_CATALOGUE_NOT_GIVEN" in capsys.readouterr().out


def test_build_writes_the_model(tmp_path, capsys):
    assert main(["build", FIXTURE, "--no-media", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "cpacs-doc-model.json").exists()


def test_missing_schema_exits_two():
    assert main(["report", "/does/not/exist.xsd"]) == 2
