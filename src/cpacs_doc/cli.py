"""Command line interface.

    cpacs-doc report schema/cpacs_schema.xsd
    cpacs-doc build  schema/cpacs_schema.xsd -o build/

`report` reads the schema and writes findings to the terminal. `build` does the
same and additionally writes the intermediate model. Both share one pipeline, so
the report can never describe a different run than the model does.

Exit status is 1 when the report holds errors, so CI fails on a broken schema
without a second check. `--tolerate-errors` suppresses that for exploratory runs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree

from . import catalogue as catalogue_module
from . import media as media_module
from . import model as model_module
from . import tree as tree_module
from .findings import Report

DEFAULT_MODEL_NAME = "cpacs-doc-model.json"
DEFAULT_MEDIA_NAME = "media.json"

# The tree is deep enough (22 levels, each recursing through several frames)
# that CPython's default limit of 1000 is not sufficient.
RECURSION_LIMIT = 10000

# Parser settings match cpacs-schema-tool so both tools see the same schema
# (N17). Imitation, not coupling.
PARSER = etree.XMLParser(no_network=True, strip_cdata=False, resolve_entities=False)


def run(schema_path: Path, media_path: Path | None, report: Report, *, media_expected: bool = True):
    """The single pipeline behind both subcommands.

    `media_expected` separates an absent catalogue from one deliberately
    switched off: only the former is worth a warning.
    """
    root = etree.parse(str(schema_path), PARSER).getroot()
    source = schema_path.name

    catalogue = catalogue_module.build(root, source)
    report.extend(catalogue.findings)

    tree = tree_module.build(root, catalogue, source)
    report.extend(tree.findings)

    referenced_ids: set[str] = set()
    for info in catalogue.types.values():
        referenced_ids |= info.doc.image_ids
    for node in tree.walk():
        referenced_ids |= node.doc.image_ids

    media_catalogue = None
    if media_path is not None:
        media_catalogue = media_module.load(media_path)
        report.extend(media_catalogue.findings)
        report.extend(media_module.validate(media_catalogue, referenced_ids))
    elif media_expected and referenced_ids:
        report.warning(
            "MEDIA_CATALOGUE_NOT_GIVEN",
            f"{len(referenced_ids)} image ids are referenced but no media catalogue was given",
            str(schema_path),
        )

    return catalogue, tree, media_catalogue


def default_media_path(schema_path: Path) -> Path | None:
    """`documentation/media.json` as a sibling of the schema directory.

    Guessed only when it exists; an absent catalogue is reported by `run`
    rather than silently treated as empty.
    """
    candidate = schema_path.parent.parent / "documentation" / DEFAULT_MEDIA_NAME
    return candidate if candidate.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cpacs-doc", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"model {model_module.MODEL_VERSION}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    def common(sub):
        sub.add_argument("schema", type=Path, help="path to the XSD file")
        sub.add_argument("--media", type=Path, help=f"path to {DEFAULT_MEDIA_NAME}")
        sub.add_argument("--no-media", action="store_true", help="skip the media catalogue entirely")
        sub.add_argument("--limit", type=int, default=10,
                         help="findings shown per code, 0 for all (default: 10)")
        sub.add_argument("--tolerate-errors", action="store_true",
                         help="exit 0 even when the report holds errors")

    report_command = subcommands.add_parser("report", help="write the build report only")
    common(report_command)

    build_command = subcommands.add_parser("build", help="write the build report and the model")
    common(build_command)
    build_command.add_argument("-o", "--output", type=Path, default=Path("build"),
                               help="output directory (default: build)")

    args = parser.parse_args(argv)

    if not args.schema.exists():
        print(f"no such file: {args.schema}", file=sys.stderr)
        return 2

    if args.no_media:
        media_path = None
    elif args.media is not None:
        media_path = args.media
    else:
        media_path = default_media_path(args.schema)

    sys.setrecursionlimit(RECURSION_LIMIT)
    report = Report()

    try:
        catalogue, tree, media_catalogue = run(
            args.schema, media_path, report, media_expected=not args.no_media
        )
    except etree.XMLSyntaxError as err:
        print(f"cannot parse {args.schema}: {err}", file=sys.stderr)
        return 2

    if args.command == "build":
        model = model_module.build(
            catalogue,
            tree,
            media_catalogue,
            report,
            schema_path=str(args.schema),
            schema_version=None,
        )
        written = model_module.write(model, args.output / DEFAULT_MODEL_NAME)
        print(f"model: {written} ({written.stat().st_size / 1e6:.1f} MB)")

    _write_statistics(catalogue, tree, media_catalogue)
    report.write(sys.stdout, limit=None if args.limit == 0 else args.limit)

    return 1 if report.failed and not args.tolerate_errors else 0


def _write_statistics(catalogue, tree, media_catalogue) -> None:
    documented = sum(1 for t in catalogue.types.values() if t.documented)
    print(
        f"types: {len(catalogue.types)} ({documented} documented) | "
        f"tree: {tree.nodes} nodes, {tree.distinct_paths} distinct paths, depth {tree.max_depth} | "
        f"media: {len(media_catalogue.entries) if media_catalogue else 0} entries"
    )


if __name__ == "__main__":
    sys.exit(main())
