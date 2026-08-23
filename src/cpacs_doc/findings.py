"""Findings and the build report (N10).

Every component of the extractor reports what it cannot decide from the schema
rather than resolving it by assumption. The report is the primary deliverable of
phase 1: it turns undocumented types, unknown vocabulary, unresolvable figures
and structural outliers into an actionable list.

Findings are collected, never raised. A single malformed annotation must not
abort a run whose purpose is to enumerate all such cases.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, TextIO

ERROR = "error"
WARNING = "warning"
INFO = "info"

_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    location: str = ""

    def __post_init__(self):
        if self.severity not in _ORDER:
            raise ValueError(f"unknown severity: {self.severity!r}")


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    _seen: set[Finding] = field(default_factory=set, repr=False)

    def add(self, severity: str, code: str, message: str, location: str = "") -> None:
        self._append(Finding(severity, code, message, location))

    def _append(self, finding: Finding) -> None:
        # One schema defect is one entry. Several stages may reach the same
        # construct, and a report that counts a defect by how often it was
        # visited misstates its scale.
        if finding in self._seen:
            return
        self._seen.add(finding)
        self.findings.append(finding)

    def error(self, code: str, message: str, location: str = "") -> None:
        self.add(ERROR, code, message, location)

    def warning(self, code: str, message: str, location: str = "") -> None:
        self.add(WARNING, code, message, location)

    def info(self, code: str, message: str, location: str = "") -> None:
        self.add(INFO, code, message, location)

    def extend(self, findings: Iterable[Finding]) -> None:
        for finding in findings:
            self._append(finding)

    @property
    def counts(self) -> Counter:
        return Counter(f.severity for f in self.findings)

    @property
    def failed(self) -> bool:
        return self.counts[ERROR] > 0

    def by_code(self) -> dict[str, list[Finding]]:
        grouped: dict[str, list[Finding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.code, []).append(finding)
        return grouped

    def write(self, stream: TextIO = sys.stdout, limit: int | None = 10) -> None:
        """Human-readable report, grouped by code, severest group first.

        Codes with many occurrences are truncated: a schema-wide defect produces
        hundreds of identical lines, and a report nobody reads to the end is a
        report nobody acts on. `limit=None` prints everything.
        """
        grouped = self.by_code()
        if not grouped:
            stream.write("no findings\n")
            return

        def rank(item):
            code, findings = item
            worst = min(_ORDER[f.severity] for f in findings)
            return worst, -len(findings), code

        for code, findings in sorted(grouped.items(), key=rank):
            worst = min(findings, key=lambda f: _ORDER[f.severity]).severity
            stream.write(f"\n{worst.upper()}  {code}  ({len(findings)})\n")
            shown = findings if limit is None else findings[:limit]
            for finding in shown:
                where = f"  [{finding.location}]" if finding.location else ""
                stream.write(f"    {finding.message}{where}\n")
            if limit is not None and len(findings) > limit:
                stream.write(f"    … {len(findings) - limit} more\n")

        counts = self.counts
        stream.write(
            f"\n{counts[ERROR]} errors, {counts[WARNING]} warnings, {counts[INFO]} notes\n"
        )

    def to_json(self) -> list[dict]:
        """Serialised into the model so the viewer can surface the same list."""
        return [
            {
                "severity": f.severity,
                "code": f.code,
                "message": f.message,
                "location": f.location,
            }
            for f in self.findings
        ]
