"""Command line interface.

    cpacs-doc report schema/cpacs_schema.xsd
    cpacs-doc build  schema/cpacs_schema.xsd -o build/
    cpacs-doc serve  schema/cpacs_schema.xsd

`report` reads the schema and writes findings to the terminal. `build` does the
same and additionally writes the intermediate model. `serve` builds the model in
memory and serves the viewer from it, rebuilding when the schema changes (R4).
All three share one pipeline, so the report can never describe a different run
than the model does.

Exit status is 1 when the report holds errors, so CI fails on a broken schema
without a second check. `--tolerate-errors` suppresses that for exploratory runs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lxml import etree

from . import catalogue as catalogue_module
from . import content as content_module
from . import generator as generator_module
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

    content_by_type = {}
    for name, info in catalogue.types.items():
        entry = content_module.read(info, catalogue, source)
        report.extend(entry.findings)
        if not entry.is_empty:
            content_by_type[name] = entry

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

    return catalogue, tree, media_catalogue, content_by_type


def root_version(schema_path: Path, report: Report) -> str | None:
    """`version` on `xsd:schema`, where the schema carries one.

    Its absence is reported, not worked around: deriving a version from a
    documentation body or from the file name would be a guess, and generating
    is version-free by design.
    """
    root = etree.parse(str(schema_path), PARSER).getroot()
    version = root.get("version")
    if not version:
        report.info(
            "SCHEMA_WITHOUT_VERSION",
            "xsd:schema carries no version attribute; the model records none",
            str(schema_path),
        )
        return None
    return version


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

    def common(sub, *, exits_on_errors: bool = True):
        sub.add_argument("schema", type=Path, help="path to the XSD file")
        sub.add_argument("--media", type=Path, help=f"path to {DEFAULT_MEDIA_NAME}")
        sub.add_argument("--no-media", action="store_true", help="skip the media catalogue entirely")
        sub.add_argument("--limit", type=int, default=10,
                         help="findings shown per code, 0 for all (default: 10)")
        # `serve` runs until interrupted and has no verdict to carry in an exit
        # code, so the flag that suppresses one does not apply to it.
        if exits_on_errors:
            sub.add_argument("--tolerate-errors", action="store_true",
                             help="exit 0 even when the report holds errors")

    report_command = subcommands.add_parser("report", help="write the build report only")
    common(report_command)

    build_command = subcommands.add_parser("build", help="write the build report and the model")
    common(build_command)
    build_command.add_argument("-o", "--output", type=Path, default=Path("build"),
                               help="output directory (default: build)")
    build_command.add_argument("--site", action="store_true",
                               help="also write the static type pages")
    build_command.add_argument("--media-root", type=Path,
                               help="directory the media catalogue paths are relative to "
                                    "(default: the catalogue's own directory)")

    serve_command = subcommands.add_parser("serve", help="serve the viewer and rebuild on change")
    common(serve_command, exits_on_errors=False)
    serve_command.add_argument("--host", default="127.0.0.1",
                               help="address to bind (default: 127.0.0.1)")
    serve_command.add_argument("--port", type=int, default=8000,
                               help="port to bind, 0 for any free port (default: 8000)")
    serve_command.add_argument("--media-root", type=Path,
                               help="directory the media catalogue paths are relative to "
                                    "(default: the catalogue's own directory)")

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

    if args.command == "serve":
        # Imported here rather than at module scope: the server runs this
        # module's pipeline, so a top-level import would close a cycle.
        from . import serve as serve_module

        return serve_module.serve(
            args.schema,
            media_path,
            media_expected=not args.no_media,
            media_root=args.media_root,
            limit=None if args.limit == 0 else args.limit,
            host=args.host,
            port=args.port,
        )

    report = Report()

    try:
        catalogue, tree, media_catalogue, content_by_type = run(
            args.schema, media_path, report, media_expected=not args.no_media
        )
    except etree.XMLSyntaxError as err:
        print(f"cannot parse {args.schema}: {err}", file=sys.stderr)
        return 2

    if args.command == "build":
        rendered, render_findings = model_module.render_all(
            catalogue, media_catalogue, args.schema.name
        )
        report.extend(render_findings)
        model = model_module.build(
            catalogue,
            tree,
            media_catalogue,
            report,
            schema_path=str(args.schema),
            schema_version=root_version(args.schema, report),
            content_by_type=content_by_type,
            rendered=rendered,
        )
        written = model_module.write(model, args.output / DEFAULT_MODEL_NAME)
        print(f"model: {written} ({written.stat().st_size / 1e6:.1f} MB)")

        if args.site:
            media_root = args.media_root
            if media_root is None and media_catalogue is not None:
                media_root = media_catalogue.base_dir
            site = generator_module.generate(model, args.output, media_root=media_root)
            report.extend(site.findings)
            print(f"site: {args.output} ({site.pages} pages, {site.assets} figures)")

    _write_statistics(catalogue, tree, media_catalogue)
    report.write(sys.stdout, limit=None if args.limit == 0 else args.limit)

    return 1 if report.failed and not args.tolerate_errors else 0


def _write_statistics(catalogue, tree, media_catalogue) -> None:
    documented = sum(1 for t in catalogue.types.values() if t.documented)
    print(
        f"types: {len(catalogue.types)} ({documented} documented) | "
        f"tree: {tree.nodes} nodes ({tree.alternatives} in a choice), "
        f"{tree.distinct_paths} distinct paths, depth {tree.max_depth} | "
        f"media: {len(media_catalogue.entries) if media_catalogue else 0} entries"
    )


if __name__ == "__main__":
    sys.exit(main())
