"""The generator: static type pages plus the assets they need.

One page per type, written as a real file so it answers with HTTP 200 and can be
cited (G3). Tree paths are not files — they are resolved client-side by the
router, which is why only type pages exist here.

Everything is relative to the output root. The pages sit at a known depth, so
their links and image sources resolve regardless of where the directory is
deployed. Nothing here needs to know the deployment prefix or the schema
version.
"""

from __future__ import annotations

import shutil
from importlib import resources
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from .findings import Finding

# Anonymous types are named after their owning element and therefore contain a
# slash. Two hyphens are reversible, occur in no real type name, and stay
# readable in a URL — checked against all 1,206 catalogue entries.
PATH_SEPARATOR = "--"

TYPES_DIRECTORY = "type"
MEDIA_DIRECTORY = "media"
ASSET_DIRECTORY = "assets"

STYLESHEET = "styles.css"

# "sequence" and "all" are schema words for a distinction that matters to anyone
# writing an instance: whether the children must appear in the given order.
COMPOSITOR_LABEL = {
    "sequence": "children in fixed order",
    "all": "children in any order",
    "choice": "one of the children",
}

# Substituted for the path back to the output root in rendered fragments.
ROOT_TOKEN = "%ROOT%"


def slug(type_name: str) -> str:
    return type_name.replace("/", PATH_SEPARATOR)


def unslug(value: str) -> str:
    return value.replace(PATH_SEPARATOR, "/")


@dataclass
class GeneratorResult:
    pages: int = 0
    assets: int = 0
    findings: list[Finding] = field(default_factory=list)


def generate(model: dict, output: Path, *, media_root: Path | None = None) -> GeneratorResult:
    """Write the static site into `output`."""
    result = GeneratorResult()
    output = Path(output)
    (output / TYPES_DIRECTORY).mkdir(parents=True, exist_ok=True)

    _write_assets(output / ASSET_DIRECTORY)
    _write_router(output)

    types = model.get("types", {})
    for name, entry in sorted(types.items()):
        html = _type_page(name, entry, types, model.get("firstPaths", {}))
        target = output / TYPES_DIRECTORY / slug(name) / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        result.pages += 1

    _write_index(output, types, model.get("statistics", {}), model.get("meta", {}))
    result.assets = _copy_media(model, output, media_root, result)
    return result


def _copy_media(model, output, media_root, result) -> int:
    media = model.get("media", {})
    if not media:
        return 0
    if media_root is None:
        result.findings.append(
            Finding(
                "warning",
                "GENERATOR_MEDIA_ROOT_MISSING",
                f"{len(media)} figures are referenced but no media root was given; "
                f"images will not resolve",
                str(output),
            )
        )
        return 0

    copied = 0
    for image_id, entry in sorted(media.items()):
        source = Path(media_root) / entry["file"]
        target = output / MEDIA_DIRECTORY / entry["file"]
        if not source.exists():
            result.findings.append(
                Finding("error", "GENERATOR_MEDIA_MISSING", f"{image_id}: {source} not found", str(output))
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    return copied


def _document(title: str, depth: int, body: str) -> str:
    """Wrap a body in the page shell.

    `depth` is how far the page sits below the output root; asset links are
    built from it so the directory stays movable.
    """
    up = "../" * depth
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f'<link rel="stylesheet" href="{up}{ASSET_DIRECTORY}/{STYLESHEET}">\n'
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def _type_page(name: str, entry: dict, types: dict, first_paths: dict) -> str:
    documentation = entry.get("documentation", {})
    parts = [
        _page_nav(name, first_paths),
        f"<h1>{escape(name)}</h1>",
        _kind_line(entry),
    ]

    summary = documentation.get("summaryHtml")
    if summary:
        parts.append(f'<div class="cd-summary">{summary}</div>')
    remarks = documentation.get("remarksHtml")
    if remarks:
        parts.append(f'<div class="cd-remarks">{remarks}</div>')

    parts.append(_attribute_table(entry.get("attributes", [])))
    parts.append(_child_table(entry.get("children", [])))
    parts.append(_enumeration_list(entry.get("enumeration", [])))
    parts.append(_source_line(entry))

    body = "\n".join(p for p in parts if p)
    return _substitute_root(_resolve_cross_references(_document(name, 2, body), types), depth=2)


def _substitute_root(html: str, depth: int) -> str:
    """Resolve the renderer's root placeholder against this page's depth."""
    return html.replace(ROOT_TOKEN, ("../" * depth).rstrip("/") or ".")


def _page_nav(name: str, first_paths: dict) -> str:
    """Index link, plus a way into the tree where the type appears in one.

    Someone arriving from a cited URL sees the documentation but has no route
    into the structure. 106 of the 1,206 types are anonymous inline types that
    never appear as an element's type; those get no link rather than one that
    leads nowhere.
    """
    parts = ['<a href="../../index.html">Types</a>']
    path = first_paths.get(name)
    if path:
        parts.append(f'<a href="../../tree/{escape(path)}/">Show in tree</a>')
    return f'<nav class="cd-breadcrumb">{" · ".join(parts)}</nav>'


def _kind_line(entry) -> str:
    bits = [escape(entry.get("kind", ""))]
    base = entry.get("base")
    if base:
        derivation = entry.get("derivation") or "derives from"
        target = _type_link(base)
        bits.append(f"{escape(derivation)} {target}")
    compositor = entry.get("compositor")
    if compositor:
        bits.append(escape(COMPOSITOR_LABEL.get(compositor, compositor)))
    return f'<p class="cd-kind">{" · ".join(bits)}</p>'


def _type_link(type_name: str) -> str:
    """A link from one type page to another, or plain text for built-in types.

    Type pages are siblings under `type/`, so one level up is enough.
    """
    if not type_name or type_name.startswith("xsd:"):
        return f"<code>{escape(type_name or '')}</code>"
    return f'<a href="../{escape(slug(type_name))}/index.html"><code>{escape(type_name)}</code></a>'


def _attribute_table(attributes) -> str:
    if not attributes:
        return ""
    rows = []
    for attribute in attributes:
        origin = (
            f'<span class="cd-inherited">{escape(attribute["declaredIn"])}</span>'
            if attribute.get("inherited")
            else ""
        )
        default = attribute.get("default") or attribute.get("fixed") or ""
        rows.append(
            "<tr>"
            f'<td><code>@{escape(attribute["name"])}</code></td>'
            f'<td>{_type_link(attribute.get("type"))}</td>'
            f'<td>{escape(attribute.get("use", ""))}</td>'
            f"<td>{escape(default)}</td>"
            f'<td>{escape(attribute.get("documentation", {}).get("text", ""))}</td>'
            f"<td>{origin}</td>"
            "</tr>"
        )
    return (
        '<section class="cd-attributes"><h2>Attributes</h2><table>'
        "<tr><th>Name</th><th>Type</th><th>Use</th><th>Default</th>"
        "<th>Description</th><th>Inherited from</th></tr>"
        + "".join(rows)
        + "</table></section>"
    )


def _child_table(children) -> str:
    if not children:
        return ""
    rows = []
    for child in children:
        rows.append(
            "<tr>"
            f'<td><code>{escape(child["name"])}</code></td>'
            f'<td>{_type_link(child.get("type"))}</td>'
            f"<td>{escape(_cardinality(child))}</td>"
            f'<td>{escape(COMPOSITOR_LABEL.get(child.get("compositor"), child.get("compositor") or ""))}</td>'
            f'<td>{escape(child.get("documentation", {}).get("text", ""))}</td>'
            "</tr>"
        )
    return (
        '<section class="cd-children"><h2>Child elements</h2><table>'
        "<tr><th>Name</th><th>Type</th><th>Occurrence</th><th>Order</th><th>Description</th></tr>"
        + "".join(rows)
        + "</table></section>"
    )


def _cardinality(child) -> str:
    minimum = child.get("minOccurs", 1)
    maximum = child.get("maxOccurs", 1)
    upper = "∞" if maximum is None else str(maximum)
    return f"{minimum}…{upper}" if str(minimum) != upper else str(minimum)


def _enumeration_list(values) -> str:
    if not values:
        return ""
    rows = []
    for value in values:
        description = value.get("documentation", {}).get("text", "")
        rows.append(
            f'<tr><td><code>{escape(value["value"])}</code></td><td>{escape(description)}</td></tr>'
        )
    return (
        '<section class="cd-enumeration"><h2>Allowed values</h2><table>'
        "<tr><th>Value</th><th>Description</th></tr>" + "".join(rows) + "</table></section>"
    )


def _source_line(entry) -> str:
    # The bare line number was noise: it is not a link, and nobody reads the
    # schema by line. A real link into the schema repository would be worth
    # having; a number on its own is not.
    return ""


def _resolve_cross_references(html: str, types: dict) -> str:
    """Turn the renderer's `cd-xref` markers into links.

    The renderer records the target type name but not a URL, because it does not
    know the page layout. Resolution happens here, where it does.
    """
    import re

    def replace(match):
        target = match.group(1)
        if target not in types:
            return f"<code>{escape(target)}</code>"
        return f'<a href="../{escape(slug(target))}/index.html"><code>{escape(target)}</code></a>'

    return re.sub(
        r'<span class="cd-xref" data-type="([^"]+)">[^<]*</span>',
        replace,
        html,
    )


def _write_index(output: Path, types: dict, statistics: dict, meta: dict) -> None:
    items = "".join(
        f'<li><a href="{TYPES_DIRECTORY}/{escape(slug(name))}/index.html">{escape(name)}</a></li>'
        for name in sorted(types)
    )
    version = meta.get("schemaVersion")
    heading = f"CPACS {escape(version)}" if version else "CPACS schema"
    summary = (
        f'<p class="cd-kind">{statistics.get("types", 0)} types · '
        f'{statistics.get("distinctPaths", 0)} instance paths · '
        f'depth {statistics.get("maxDepth", 0)}</p>'
    )
    body = f"<h1>{heading}</h1>{summary}<ul class=\"cd-type-index\">{items}</ul>"
    (output / "index.html").write_text(_substitute_root(_document(heading, 0, body), depth=0), encoding="utf-8")


ASSET_FILES = ("styles.css", "viewer.js")


def _asset(name: str) -> str:
    return resources.files(__package__).joinpath("assets", name).read_text(encoding="utf-8")


def _write_assets(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in ASSET_FILES:
        (directory / name).write_text(_asset(name), encoding="utf-8")


def _write_router(output: Path) -> None:
    """The single not-found document that serves every tree path.

    Its stylesheet is inlined rather than linked: the page is served from
    arbitrary depth and cannot resolve a relative URL, and it does not know its
    own root until the script has run. The script is inlined for the same
    reason — loading it by absolute URL would need the root first.
    """
    html = (
        "<!doctype html>\n"
        '<html lang="en">\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>CPACS schema</title>\n"
        f"<style>\n{_asset('styles.css')}</style>\n"
        '<body class="cd-viewer">\n<div id="cd-app" class="cd-app">\n'
        '<div id="cd-tree" class="cd-pane"></div>\n'
        '<div id="cd-splitter" class="cd-splitter" role="separator" aria-orientation="vertical"'
        ' tabindex="0" aria-label="Resize the tree pane"></div>\n'
        '<div id="cd-detail" class="cd-pane cd-pane-detail"></div>\n'
        "</div>\n"
        f"<script>\n{_asset('viewer.js')}</script>\n"
        "</body>\n</html>\n"
    )
    (output / "404.html").write_text(html, encoding="utf-8")
