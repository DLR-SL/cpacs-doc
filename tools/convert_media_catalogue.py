#!/usr/bin/env python3
"""Convert the SHFB image catalogue into `media.json`.

The mapping from figure id to file currently lives in the SHFB project file,
which the new toolchain is meant to shed. This is a one-off migration, not part
of the build: run it once, commit the result, and the `.shfbproj` is no longer
needed for figures.

Case is corrected against the file system on the way. Four entries in the
existing catalogue differ from their files only in capitalisation, which
resolves on Windows and fails on a Linux runner.

Usage:
    ./convert_media_catalogue.py documentation/
    ./convert_media_catalogue.py documentation/ --dry-run

Standard library only.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

IMAGE = re.compile(r'<Image Include="([^"]+)"\s*>(.*?)</Image>', re.S)
IMAGE_ID = re.compile(r"<ImageId>([^<]*)</ImageId>")
ALTERNATE_TEXT = re.compile(r"<AlternateText>([^<]*)</AlternateText>")

CATALOGUE_VERSION = 1


def actual_case(base: Path, relative: str) -> str | None:
    """The path as it exists on disk, or None if nothing matches.

    Compared against directory listings rather than through `Path.exists()`,
    which is case-insensitive on Windows and macOS and would therefore accept
    the very spellings this conversion exists to correct. Segment by segment,
    because a directory may differ in case just as a file may.
    """
    current = base
    parts = []
    for wanted in Path(relative).parts:
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


def convert(documentation: Path):
    projects = sorted(documentation.glob("*.shfbproj"))
    if not projects:
        raise SystemExit(f"no .shfbproj found in {documentation}")
    project = projects[0]

    text = project.read_text(encoding="utf-8-sig")
    images = {}
    problems = []

    for raw_path, body in IMAGE.findall(text):
        image_id = IMAGE_ID.search(body)
        if not image_id:
            problems.append(f"entry without <ImageId>: {raw_path}")
            continue
        image_id = image_id.group(1)

        alternate = ALTERNATE_TEXT.search(body)
        if not alternate or not alternate.group(1).strip():
            problems.append(f"{image_id}: no AlternateText; alt is mandatory in media.json")
            continue

        relative = raw_path.replace("\\", "/")
        corrected = actual_case(documentation, relative)
        if corrected is None:
            problems.append(f"{image_id}: file not found: {relative}")
            continue
        if corrected != relative:
            problems.append(f"{image_id}: case corrected {relative} -> {corrected}")

        if image_id in images:
            problems.append(f"{image_id}: declared more than once")
            continue

        images[image_id] = {"file": corrected, "alt": alternate.group(1).strip()}

    return project, images, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("documentation", type=Path, help="directory holding the .shfbproj and the figures")
    parser.add_argument("-o", "--output", type=Path, help="output file (default: <documentation>/media.json)")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    project, images, problems = convert(args.documentation)
    output = args.output or args.documentation / "media.json"

    print(f"source: {project.name}")
    print(f"entries: {len(images)}")
    for problem in problems:
        print(f"  {problem}")

    if args.dry_run:
        print("(dry run, nothing written)")
        return 0

    payload = {"schemaVersion": CATALOGUE_VERSION, "images": dict(sorted(images.items()))}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written: {output}")

    # Entries dropped for a missing file or a missing alt text are not carried
    # over silently; a catalogue that is quietly shorter than its source is
    # worse than one that refuses to be written.
    dropped = [p for p in problems if "case corrected" not in p]
    return 1 if dropped else 0


if __name__ == "__main__":
    sys.exit(main())
