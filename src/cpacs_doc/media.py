"""Media catalogue: loading, validation, and resolution of figure references.

The schema references figures by id via `ddue:image/@xlink:href`. The mapping
from id to file lives outside the schema, in `documentation/media.json`. This
module is the only place that knows that format.

Every problem is reported rather than repaired: a missing file, an unknown id,
or a malformed entry yields a finding for the build report. Nothing is guessed
from naming conventions, because ten of the existing ids deliberately differ
from their file names.
"""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SUPPORTED_CATALOGUE_VERSION = 1


@dataclass(frozen=True)
class Finding:
    """One entry in the build report (N10)."""

    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    location: str = ""


@dataclass(frozen=True)
class MediaEntry:
    image_id: str
    file: str  # POSIX-style, relative to the catalogue directory
    alt: str


@dataclass
class MediaCatalogue:
    path: Path
    entries: dict[str, MediaEntry] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def base_dir(self) -> Path:
        return self.path.parent

    def resolve(self, image_id: str) -> MediaEntry | None:
        return self.entries.get(image_id)

    def file_path(self, entry: MediaEntry) -> Path:
        return self.base_dir / PurePosixPath(entry.file)


def load(path: str | Path) -> MediaCatalogue:
    """Read a catalogue. Structural problems become findings, not exceptions."""
    path = Path(path)
    catalogue = MediaCatalogue(path=path)

    if not path.exists():
        catalogue.findings.append(
            Finding(
                "error",
                "MEDIA_CATALOGUE_MISSING",
                f"media catalogue not found: {path}",
                str(path),
            )
        )
        return catalogue

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        catalogue.findings.append(
            Finding("error", "MEDIA_CATALOGUE_UNREADABLE", str(err), str(path))
        )
        return catalogue

    version = data.get("schemaVersion")
    if version != SUPPORTED_CATALOGUE_VERSION:
        catalogue.findings.append(
            Finding(
                "error",
                "MEDIA_CATALOGUE_VERSION",
                f"schemaVersion {version!r} is not supported "
                f"(expected {SUPPORTED_CATALOGUE_VERSION})",
                str(path),
            )
        )
        return catalogue

    images = data.get("images")
    if not isinstance(images, dict):
        catalogue.findings.append(
            Finding("error", "MEDIA_CATALOGUE_MALFORMED", "'images' must be an object", str(path))
        )
        return catalogue

    for image_id, raw in sorted(images.items()):
        entry = _read_entry(image_id, raw, str(path), catalogue.findings)
        if entry is not None:
            catalogue.entries[image_id] = entry

    return catalogue


def _read_entry(image_id, raw, where, findings) -> MediaEntry | None:
    if not isinstance(raw, dict):
        findings.append(
            Finding("error", "MEDIA_ENTRY_MALFORMED", f"{image_id}: entry must be an object", where)
        )
        return None

    file = raw.get("file")
    alt = raw.get("alt")

    if not isinstance(file, str) or not file:
        findings.append(
            Finding("error", "MEDIA_ENTRY_MALFORMED", f"{image_id}: 'file' missing or empty", where)
        )
        return None
    # alt is mandatory: every one of the existing entries carries one, and making
    # it optional is how the next figure ends up without an accessible name.
    if not isinstance(alt, str) or not alt.strip():
        findings.append(
            Finding("error", "MEDIA_ENTRY_NO_ALT", f"{image_id}: 'alt' missing or empty", where)
        )
        return None

    if "\\" in file:
        findings.append(
            Finding(
                "error",
                "MEDIA_PATH_NOT_PORTABLE",
                f"{image_id}: 'file' must use forward slashes: {file!r}",
                where,
            )
        )
        return None
    if posixpath.isabs(file) or ".." in PurePosixPath(file).parts:
        findings.append(
            Finding(
                "error",
                "MEDIA_PATH_NOT_CONTAINED",
                f"{image_id}: 'file' must be relative to the catalogue and stay below it: {file!r}",
                where,
            )
        )
        return None

    return MediaEntry(image_id=image_id, file=file, alt=alt.strip())


def actual_path(base: Path, relative: str) -> str | None:
    """The path as the file system actually spells it, or None if absent.

    Compared against directory listings segment by segment rather than through
    `Path.exists()`: that call is case-insensitive on Windows and macOS, so a
    name differing only in case would be reported as present on the machine the
    catalogue is edited on and as missing on the Linux runner that publishes it.
    Directories are checked too, not just the file name.
    """
    current = base
    parts: list[str] = []
    for wanted in PurePosixPath(relative).parts:
        if not current.is_dir():
            return None
        matches = [c.name for c in current.iterdir() if c.name == wanted]
        if not matches:
            matches = [c.name for c in current.iterdir() if c.name.lower() == wanted.lower()]
            if len(matches) != 1:
                return None
        parts.append(matches[0])
        current = current / matches[0]
    return "/".join(parts)


def validate(catalogue: MediaCatalogue, referenced_ids: set[str]) -> list[Finding]:
    """Cross-check the catalogue against the schema's references and the disk."""
    findings: list[Finding] = []
    where = str(catalogue.path)

    for image_id in sorted(referenced_ids - set(catalogue.entries)):
        findings.append(
            Finding(
                "error",
                "MEDIA_ID_UNRESOLVED",
                f"schema references image id {image_id!r}, which the catalogue does not define",
                where,
            )
        )

    for image_id in sorted(set(catalogue.entries) - referenced_ids):
        findings.append(
            Finding(
                "info",
                "MEDIA_ENTRY_UNREFERENCED",
                f"catalogue defines {image_id!r}, which no documentation references",
                where,
            )
        )

    seen: dict[str, str] = {}
    for image_id, entry in sorted(catalogue.entries.items()):
        actual = actual_path(catalogue.base_dir, entry.file)
        if actual is None:
            findings.append(
                Finding(
                    "error" if image_id in referenced_ids else "warning",
                    "MEDIA_FILE_ABSENT",
                    f"{image_id}: file not found: {entry.file}",
                    where,
                )
            )
        elif actual != entry.file:
            findings.append(
                Finding(
                    "error",
                    "MEDIA_FILE_CASE_MISMATCH",
                    f"{image_id}: catalogue says {entry.file!r}, on disk it is {actual!r} — "
                    f"resolves on case-insensitive file systems only",
                    where,
                )
            )
        # Two ids pointing at one file is legitimate; two entries differing only
        # in case are not, because deployment targets are case-sensitive while
        # some development file systems are not.
        lowered = entry.file.lower()
        if lowered in seen and seen[lowered] != entry.file:
            findings.append(
                Finding(
                    "error",
                    "MEDIA_PATH_CASE_COLLISION",
                    f"{image_id}: {entry.file!r} collides with {seen[lowered]!r} on case-insensitive file systems",
                    where,
                )
            )
        seen.setdefault(lowered, entry.file)

    return findings
