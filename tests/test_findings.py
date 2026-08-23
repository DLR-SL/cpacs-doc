from cpacs_doc.findings import Report


def test_identical_findings_are_counted_once():
    report = Report()
    report.error("CODE", "same message", "file:1")
    report.error("CODE", "same message", "file:1")
    assert len(report.findings) == 1


def test_findings_differing_in_location_are_kept():
    report = Report()
    report.error("CODE", "same message", "file:1")
    report.error("CODE", "same message", "file:2")
    assert len(report.findings) == 2


def test_exit_state_follows_errors_only():
    report = Report()
    report.warning("CODE", "not fatal")
    report.info("CODE", "not fatal either")
    assert not report.failed
    report.error("CODE", "fatal")
    assert report.failed
