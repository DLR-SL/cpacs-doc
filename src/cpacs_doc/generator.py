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
DOC_DIRECTORY = "doc"
MEDIA_DIRECTORY = "media"
ASSET_DIRECTORY = "assets"

STYLESHEET = "styles.css"

# Substituted for the path back to the output root in rendered fragments.
ROOT_TOKEN = "%ROOT%"


def slug(type_name: str) -> str:
    return type_name.replace("/", PATH_SEPARATOR)


def unslug(value: str) -> str:
    return value.replace(PATH_SEPARATOR, "/")


@dataclass
class GeneratorResult:
    pages: int = 0
    docs: int = 0
    assets: int = 0
    findings: list[Finding] = field(default_factory=list)


def generate(model: dict, output: Path, *, media_root: Path | None = None) -> GeneratorResult:
    """Write the static site into `output`."""
    result = GeneratorResult()
    output = Path(output)
    (output / TYPES_DIRECTORY).mkdir(parents=True, exist_ok=True)

    _write_assets(output / ASSET_DIRECTORY)
    _write_router(output)

    documentation = model.get("documentation") or {}
    sections = documentation.get("sections") or []
    result.docs = _write_docs(output, sections, model.get("types", {}), documentation.get("type"))

    types = model.get("types", {})
    usage = usage_index(model)
    for name, entry in sorted(types.items()):
        html = type_page(
            name, entry, types, model.get("firstPaths", {}),
            sections=sections if name == documentation.get("type") else (),
            usage=usage,
        )
        target = output / TYPES_DIRECTORY / slug(name) / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        result.pages += 1

    _write_index(output, types, model.get("statistics", {}), model.get("meta", {}),
                 has_docs=bool(sections))
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


# Longer lists say nothing a count does not. The search shows sixty of a
# thousand for the same reason.
USAGE_LIMIT = 25


def members_of(children) -> list:
    """Element members of a child list, groups walked through."""
    found = []
    stack = list(children)
    while stack:
        member = stack.pop()
        if member.get("kind") == "group":
            stack.extend(member.get("members", []))
        elif member.get("kind") != "any":
            found.append(member)
    return found


def usage_index(model: dict) -> dict:
    """Who names each type, and how often it occurs in the tree.

    Derived here rather than carried in the model, for the reason decision 0009
    gives about the search index: both facts are already in the model — the
    references in `types[*].children[*].type`, the occurrences in the tree —
    and a second copy would be 8.3 MB of instance paths to keep in step with
    the first. The viewer derives the same two facts the same way.
    """
    users: dict[str, list[tuple[str, str]]] = {}
    for name, entry in model.get("types", {}).items():
        for member in members_of(entry.get("children", [])):
            if member.get("type"):
                users.setdefault(member["type"], []).append((name, member["name"]))
        for attribute in entry.get("attributes", []):
            if attribute.get("type"):
                users.setdefault(attribute["type"], []).append(
                    (name, "@" + attribute["name"])
                )

    # The paths themselves, up to the cap, and how many there are in all: what
    # a reader wants first is where the type stands in a document, and only the
    # few types that are everywhere need the number instead.
    paths: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    declarations = model.get("declarations", {})
    stack = [(model["tree"], "")] if model.get("tree") else []
    while stack:
        node, prefix = stack.pop()
        declaration = declarations.get(node.get("d"), {})
        here = f"{prefix}/{declaration.get('name', '?')}".lstrip("/")
        name = declaration.get("type")
        if name:
            counts[name] = counts.get(name, 0) + 1
            if len(paths.setdefault(name, [])) < USAGE_LIMIT:
                paths[name].append(here)
        # Pushed in reverse so they come off in document order: the list is
        # capped, and "and N more" has to mean the ones after these.
        for child in reversed(node.get("children", [])):
            stack.append((child, here))

    return {"users": users, "paths": paths, "counts": counts}


def _usage_section(name: str, usage: dict, first_paths: dict) -> str:
    """Where a type is used: by which declarations, and at how many paths.

    The list holds declarations because that answer stays human-sized — 84 % of
    the types in CPACS 3.5.1 are named exactly once — while the same type can
    sit at 28,120 instance paths, which is a number rather than a list.
    """
    users = sorted(set(usage.get("users", {}).get(name, [])))
    paths = usage.get("paths", {}).get(name, [])
    count = usage.get("counts", {}).get(name, 0)
    if not users and not count:
        return ""

    # A table, not a list: the names would start at a different column on
    # every line, and twenty-five of those read as a jumble. Every other pair
    # on these pages is a table for the same reason.
    rows = "".join(
        f'<tr><td><a href="../{escape(slug(owner))}/index.html">'
        f"<code>{escape(owner)}</code></a></td>"
        f"<td><code>{escape(member)}</code></td></tr>"
        for owner, member in users[:USAGE_LIMIT]
    )
    if len(users) > USAGE_LIMIT:
        rows += (f'<tr><td colspan="2" class="cd-inherited">'
                 f"and {len(users) - USAGE_LIMIT} more</td></tr>")

    # Where it stands in a document comes first: it is the concrete answer, and
    # the one neither predecessor could give. The two headings name the level
    # rather than the contents — both lists are elements, and what tells them
    # apart is that one is a document and the other is the schema.
    where = ""
    if count:
        listed = "".join(
            f'<li><a href="../../tree/{escape(path)}/"><code>{escape(path)}</code></a></li>'
            for path in paths
        )
        if count > len(paths):
            listed += f'<li class="cd-inherited">and {count - len(paths)} more</li>'
        where = (f'<h3>In a dataset <span class="cd-inherited">· {count} '
                 f'path{"s" if count != 1 else ""}</span></h3>'
                 f'<ul class="cd-usage-list">{listed}</ul>')

    schema = ""
    if users:
        schema = (f'<h3>In the schema <span class="cd-inherited">· {len(users)} '
                  f'declaration{"s" if len(users) != 1 else ""}</span></h3>'
                  + _scrolling(f"<table><tr><th>Type</th><th>Name</th></tr>{rows}</table>"))

    # A section like the ones above it, not a fold. It was folded on the
    # grounds that it is asked for now and then, which made every reader who
    # does ask pay a click at every type — and it hid the one answer neither
    # predecessor could give, where the type stands in a document.
    return (f'<section class="cd-usage"><h2>Used by</h2>'
            f"{where}{schema}</section>")


def _write_docs(output: Path, sections: list, types: dict, doc_type: str | None) -> int:
    """The general documentation, one page per section plus an index.

    Real files, like the type pages and for the same reason (G3): this is the
    prose people cite, and a citation has to answer with 200. The viewer shows
    the same sections in its panel and links here for the address.
    """
    if not sections:
        return 0
    for section in sections:
        target = output / DOC_DIRECTORY / section["slug"] / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc_page_html(section), encoding="utf-8")
    (output / DOC_DIRECTORY / "index.html").write_text(
        doc_index_html(sections, types, doc_type), encoding="utf-8"
    )
    return len(sections)


def doc_page_html(section: dict) -> str:
    body = (
        '<nav class="cd-breadcrumb"><a href="../index.html">Documentation</a>'
        ' · <a href="../../index.html">Types</a></nav>'
        f'<h1>{escape(section["title"])}</h1>'
        f'<div class="cd-remarks">{section["html"]}</div>'
    )
    return _substitute_root(_document(section["title"], 2, body), depth=2)


def doc_index_html(sections: list, types: dict, doc_type: str | None) -> str:
    # Whatever the documentation body holds besides its sections — in CPACS
    # 3.5.1 a two-row table of version and date — heads the index rather than
    # being dropped.
    around = ""
    if doc_type:
        around = types.get(doc_type, {}).get("documentation", {}).get("remarksHtml", "")
    items = "".join(
        f'<li><a href="{escape(section["slug"])}/index.html">{escape(section["title"])}</a></li>'
        for section in sections
    )
    body = (
        '<nav class="cd-breadcrumb"><a href="../index.html">Types</a></nav>'
        "<h1>Documentation</h1>"
        f'<p class="cd-kind">{len(sections)} sections'
        + (f' · <a href="../{TYPES_DIRECTORY}/{escape(slug(doc_type))}/index.html">'
           f'<code>{escape(doc_type)}</code></a>' if doc_type else "")
        + "</p>"
        f'<div class="cd-remarks">{around}</div>'
        f'<ul class="cd-doc-index">{items}</ul>'
    )
    return _substitute_root(_document("Documentation", 1, body), depth=1)


# The reader's choice of palette, applied before anything is painted and
# carried between the viewer and the static pages, which share neither a script
# nor a document. Inline in every page rather than a file of its own: a linked
# script either blocks the render or lets the wrong palette flash first, and
# this is four hundred bytes.
#
# Three states, cycled in this order. "system" is the absence of an attribute,
# so a reader who never touches it keeps following the operating system, and a
# browser with no storage or no script gets the same.
THEME_SCRIPT = """<script>
(function () {
  var KEY = "cpacs-doc.theme";
  var ORDER = ["system", "light", "dark"];
  var root = document.documentElement;

  function read() {
    try { return window.localStorage.getItem(KEY) || "system"; } catch (e) { return "system"; }
  }
  function apply(mode) {
    if (mode === "light" || mode === "dark") root.setAttribute("data-theme", mode);
    else root.removeAttribute("data-theme");
    // The attribute is enough for the tokens, which are painted with the
    // stylesheet anyway. The canvas is not: it is the browser's, and on a page
    // that links its stylesheet rather than inlining it there is a window in
    // which the sheet has not arrived and the ground is already white. Saying
    // it here closes that window.
    root.style.colorScheme = mode === "light" || mode === "dark" ? mode : "light dark";
  }
  apply(read());

  function label(mode) {
    return "Colour theme: " + mode + ". Switch to "
      + ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length] + ".";
  }
  function dress(button, mode) {
    button.setAttribute("data-mode", mode);
    button.setAttribute("aria-label", label(mode));
    button.setAttribute("title", label(mode));
  }
  function ready() {
    var button = document.getElementById("cd-theme");
    if (!button) return;
    dress(button, read());
    button.addEventListener("click", function () {
      var next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
      try { window.localStorage.setItem(KEY, next); } catch (e) { /* private mode */ }
      apply(next);
      dress(button, next);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
</script>
"""

THEME_BUTTON = (
    '<button id="cd-theme" class="cd-theme" type="button" data-mode="system"'
    ' aria-label="Colour theme"><span class="cd-theme-mark" aria-hidden="true"></span>'
    "</button>"
)


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
        f"{THEME_SCRIPT}"
        f'<link rel="stylesheet" href="{up}{ASSET_DIRECTORY}/{STYLESHEET}">\n'
        f'<body>\n<div class="cd-chrome">{THEME_BUTTON}</div>\n{body}\n</body>\n</html>\n'
    )


def type_page(name: str, entry: dict, types: dict, first_paths: dict, sections=(),
              usage=None) -> str:
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

    parts.append(_documentation_list(sections))
    parts.append(_attribute_table(entry.get("attributes", []), types))
    parts.append(_child_table(entry.get("children", []), types))
    parts.append(_union_table(entry.get("union", []), types))
    parts.append(_facet_table(entry.get("facets", [])))
    parts.append(_enumeration_list(entry.get("enumeration", [])))
    parts.append(_usage_section(name, usage or {}, first_paths))
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
    # What an instance actually writes here, where the base does not already
    # say it: `doubleConstraintBaseType` extends `doubleBaseType` extends
    # `xsd:double`, and only the last of the three answers the question.
    content_type = entry.get("contentType")
    if content_type and content_type != base:
        bits.append("value " + _builtin_cell(content_type)
                    if content_type.startswith("xsd:")
                    else f"value <code>{escape(content_type)}</code>")
    compositor = entry.get("compositor")
    if compositor:
        bits.append(escape(compositor))
    return f'<p class="cd-kind">{" · ".join(bits)}</p>'


def _holdings(entry) -> str:
    """What narrows the value behind a type link, in the schema's own words.

    A row says `xsd:string`, which is what an instance writes there and looks
    exactly like the plain string next to it — while behind the link sit three
    allowed values or a pattern the value must match. XSD calls both of these
    constraining facets, which is why one column holds them.

    Facets are named rather than counted: `pattern` says more than "1
    constraint", and 121 of the 262 marked rows carry exactly one facet — a
    column of "1 constraint" would be wallpaper. Values are counted rather than
    named, because there can be eighteen of them and they are one click away.

    Children are deliberately left out: nearly every type has some, and a
    number on nearly every row is no signal at all.
    """
    parts = []
    values = len(entry.get("enumeration", []))
    if values:
        parts.append(f"{values} value" + ("s" if values != 1 else ""))
    # A union holds neither values nor facets, so without this the one row that
    # points at one looks like a plain string with nothing behind it.
    members = len(entry.get("union", []))
    if members:
        parts.append(f"one of {members} types")
    parts.extend(dict.fromkeys(f["name"] for f in entry.get("facets", [])))
    return ", ".join(parts)


def _constraints_cell(type_name, types) -> str:
    """Linked to the same page as the type beside it.

    Two links in a row leading to one page is a small redundancy against the
    reader who does not yet know that a type name is where values live. The
    words differ — one says what may be written, the other that there are three
    of them — and the second is the one a beginner follows.
    """
    entry = (types or {}).get(type_name) or {}
    holds = _holdings(entry)
    if not holds:
        return ""
    return (f'<a class="cd-holds" href="../{escape(slug(type_name))}/index.html">'
            f"{escape(holds)}</a>")


# The built-in datatypes have no page here — they are not in the schema — and a
# reader who has to look up what `xsd:IDREF` allows leaves the documentation to
# do it. The reference is Priscilla Walmsley's XML Schema 1.0 reference at
# datypic, which is where this documentation's own language points: it explains
# each type in prose, with values that are valid and values that are not.
#
# The 46 names below are the built-in types of XSD 1.0, and each was checked to
# answer on 2026-08-30. A name that is not among them is left as text: an
# address derived for it would be a guess, and a dead link is worse than a word.
BUILTIN_REFERENCE = "https://www.datypic.com/sc/xsd/t-xsd_"
BUILTIN_DOCUMENTED = frozenset({
    "anyType", "anySimpleType", "string", "boolean", "decimal", "float",
    "double", "duration", "dateTime", "time", "date", "gYearMonth", "gYear",
    "gMonthDay", "gDay", "gMonth", "hexBinary", "base64Binary", "anyURI",
    "QName", "NOTATION", "normalizedString", "token", "language", "NMTOKEN",
    "NMTOKENS", "Name", "NCName", "ID", "IDREF", "IDREFS", "ENTITY",
    "ENTITIES", "integer", "nonPositiveInteger", "negativeInteger", "long",
    "int", "short", "byte", "nonNegativeInteger", "unsignedLong",
    "unsignedInt", "unsignedShort", "unsignedByte", "positiveInteger",
})


def builtin_reference(type_name: str) -> str:
    """The reference page for a built-in datatype, or "" where there is none."""
    if not type_name or not type_name.startswith("xsd:"):
        return ""
    local = type_name[len("xsd:"):]
    if local not in BUILTIN_DOCUMENTED:
        return ""
    # The name keeps its capitals in the address, as it does in the schema.
    return BUILTIN_REFERENCE + local + ".html"


def _builtin_cell(type_name: str) -> str:
    """The name of a built-in datatype, linked to its reference where there is
    one. It leaves the documentation, so it opens in a tab of its own rather
    than taking the reader's place in the tree with it."""
    href = builtin_reference(type_name)
    name = f"<code>{escape(type_name or '')}</code>"
    if not href:
        return name
    return (f'<a class="cd-builtin" href="{escape(href)}" target="_blank"'
            f' rel="noopener noreferrer">{name}</a>')


def _type_link(type_name: str, types: dict | None = None) -> str:
    """A link from one type page to another, or plain text for built-in types.

    Type pages are siblings under `type/`, so one level up is enough.

    An anonymous type is labelled with its base rather than its synthetic name.
    The name says where the type was declared — which the row it sits in has
    just said — while the base says what may be written there. The link stays:
    that page is where the values are.
    """
    if not type_name or type_name.startswith("xsd:"):
        return _builtin_cell(type_name)
    entry = (types or {}).get(type_name) or {}
    label = entry.get("base") or type_name if entry.get("anonymous") else type_name
    return (f'<a href="../{escape(slug(type_name))}/index.html">'
            f"<code>{escape(label)}</code></a>")


def _documentation_list(sections) -> str:
    """On the type the documentation hangs off, the sections it was split into.

    Without it the page would look as though the documentation had been lost:
    the sections are no longer in its remarks, they are pages of their own.
    """
    if not sections:
        return ""
    items = "".join(
        f'<li><a href="../../{DOC_DIRECTORY}/{escape(section["slug"])}/index.html">'
        f'{escape(section["title"])}</a></li>'
        for section in sections
    )
    return (
        '<section class="cd-documentation"><h2>Documentation</h2>'
        f'<ul class="cd-doc-index">{items}</ul></section>'
    )


def _value_cell(entry) -> str:
    """What the declaration says the value is, where it says anything.

    A default and a fixed value are not the same thing — one is what an
    instance means by leaving the element out, the other the only value it may
    write — so the cell says which it is rather than showing the bare value for
    both.
    """
    if entry.get("fixed") is not None:
        return (f'<code>{escape(entry["fixed"])}</code>'
                f' <span class="cd-fixed">fixed</span>')
    default = entry.get("default")
    return f"<code>{escape(default)}</code>" if default is not None else ""


# A table is the one thing on a type page that cannot be made to fit. The child
# table needs 1,143 px on `wingType`, 1,119 on `fuselageType` and 1,073 on
# `genericMassType` against a 928 px column — the 58 rem measure less its
# padding, at a 1280 px viewport, measured 2026-08-30. Without a container of
# its own the table is not what scrolls: it is the page, and the heading, the
# prose and the breadcrumb slide out of view with the table. So the table
# scrolls inside its section, the way a code block already does (styles.css).
def _scrolling(table: str) -> str:
    return f'<div class="cd-scroll">{table}</div>'


def _attribute_table(attributes, types=None) -> str:
    if not attributes:
        return ""
    rows = []
    for attribute in attributes:
        value = _value_cell(attribute)
        rows.append(
            "<tr>"
            f'<td><code>@{escape(attribute["name"])}</code></td>'
            f'<td>{_type_link(attribute.get("type"), types)}</td>'
            f'<td>{_constraints_cell(attribute.get("type"), types)}</td>'
            f'<td>{escape(attribute.get("use", ""))}</td>'
            f"<td>{value}</td>"
            f'<td>{escape(attribute.get("documentation", {}).get("text", ""))}</td>'
            "</tr>"
        )
    table = (
        "<table>"
        "<tr><th>Name</th><th>Type</th><th>Constraints</th><th>Use</th><th>Default</th>"
        "<th>Description</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return ('<section class="cd-attributes"><h2>Attributes</h2>'
            + _scrolling(table) + "</section>")


# The schema word carries the row; the explanation appears on hover and focus,
# so the table stays quiet for readers who already know the vocabulary.
GROUP_GLOSS = {
    "sequence": (
        "The children below must appear in exactly this order. "
        "Each may repeat as often as its own occurrence allows."
    ),
    "all": (
        "The children below may appear in any order. "
        "Each may appear at most once."
    ),
    "choice": (
        "Exactly one of the alternatives below may appear, "
        "unless the occurrence next to this line says otherwise."
    ),
}


def _child_table(children, types=None) -> str:
    if not children:
        return ""
    rows = _child_rows(children, depth=0, types=types)
    if not rows:
        return ""
    table = (
        "<table>"
        "<tr><th>Name</th><th>Type</th><th>Constraints</th>"
        f"<th>{OCCURRENCE_HEAD}</th>"
        "<th>Default</th><th>Description</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return ('<section class="cd-children"><h2>Child elements</h2>'
            + _scrolling(table) + "</section>")


# The column says how often in words; the schema says it in two attributes, and
# a reader who has the schema open needs the bridge between them.
OCCURRENCE_GLOSS = ("How often the element may appear at this place. "
                    "The schema writes it as minOccurs and maxOccurs on the declaration.")
OCCURRENCE_HEAD = ('<span class="cd-note-term" tabindex="0">Occurrence'
                   f'<span class="cd-tip" role="note">{escape(OCCURRENCE_GLOSS)}</span>'
                   "</span>")


# The one construct in the child table that is not an element and not a group.
ANY_GLOSS = "An element the schema does not name may appear here. The namespace beside it says which are allowed; strict means the element must be declared in a schema of its own."


def _child_rows(members, depth: int, types=None) -> list[str]:
    """Rows for one level, groups as headings above their indented members.

    A compositor governs a set of children, not each child on its own, so it is
    a row of its own rather than a column repeated on every line.
    """
    rows = []
    for member in members:
        # Depth travels as a custom property so one CSS rule draws the guides
        # for any nesting level, rather than a rule per level.
        indent = f' class="cd-indent" style="--depth:{depth}"' if depth else ""
        if member.get("kind") == "group":
            compositor = member.get("compositor") or ""
            suffix = (
                ""
                if _occurs_once(member)
                else f'<span class="cd-group-occurs">· {_occurrence(member)}</span>'
            )
            rows.append(
                f'<tr class="cd-group cd-group-{escape(compositor)}"><td{indent} colspan="5">'
                f'<span class="cd-group-label">'
                f'<span class="cd-group-mark" aria-hidden="true"></span>'
                f'<span class="cd-group-term" tabindex="0">{escape(compositor)}'
                f'<span class="cd-tip" role="note">{escape(GROUP_GLOSS.get(compositor, ""))}</span>'
                f"</span>{suffix}"
                f"</span></td><td></td></tr>"
            )
            rows.extend(_child_rows(member.get("members", []), depth + 1, types))
            continue
        if member.get("kind") == "any":
            # A wildcard is where the schema allows what it does not name. It
            # has no name and no type, so it borrows the row and says what it
            # does allow: a namespace, and how strictly it is checked.
            rows.append(
                "<tr>"
                f'<td{indent}><span class="cd-facet" tabindex="0">any'
                f'<span class="cd-tip" role="note">{escape(ANY_GLOSS)}</span>'
                "</span></td>"
                f'<td><code>{escape(member.get("namespace", ""))}</code></td>'
                f'<td><span class="cd-inherited">'
                f'{escape(member.get("processContents", ""))}</span></td>'
                f'<td class="cd-occurs">{_occurrence(member)}</td><td></td>'
                f'<td>{escape(member.get("documentation", {}).get("text", ""))}</td>'
                "</tr>"
            )
            continue
        rows.append(
            "<tr>"
            f'<td{indent}><code>{escape(member["name"])}</code></td>'
            f'<td>{_type_link(member.get("type"), types)}</td>'
            f'<td>{_constraints_cell(member.get("type"), types)}</td>'
            f'<td class="cd-occurs">{_occurrence(member)}</td>'
            f"<td>{_value_cell(member)}</td>"
            f'<td>{escape(member.get("documentation", {}).get("text", ""))}</td>'
            "</tr>"
        )
    return rows


def _bounds(child) -> tuple[int, int | None]:
    return child.get("minOccurs", 1), child.get("maxOccurs", 1)


def _notation(child) -> str:
    """The bounds themselves, exact for any pair the schema can hold.

    Always shown, and always first: a reader who knows the notation takes it in
    faster than a sentence, and it is the part that cannot run out of words. A
    combination this file has no phrase for still says exactly what it is.
    """
    minimum, maximum = _bounds(child)
    return f"[{minimum}..{'∞' if maximum is None else maximum}]"


# 3,663 element declarations, and 3,184 of them say one of two things: 1,527
# exactly once, 1,657 at most once. `0…1` alone said it in a notation that is
# neither XSD's own words nor anybody's plain reading. These words are the
# reading; where there is none to be had, the notation stands on its own rather
# than being padded out with a phrase nobody would write.
def _occurrence_words(child) -> str:
    minimum, maximum = _bounds(child)
    if maximum is not None and (maximum < minimum or maximum == 0):
        return ""  # nothing plain to say about a bound that forbids the element
    if maximum is None:
        if minimum == 0:
            return "any number"
        return "one or more" if minimum == 1 else f"{minimum} or more"
    if minimum == maximum:
        return "required" if minimum == 1 else f"exactly {minimum}"
    if minimum == 0:
        return "optional" if maximum == 1 else f"up to {maximum}"
    return f"{minimum} to {maximum}"


def _occurrence(child) -> str:
    """Bounds first, then the reading of them where there is one."""
    words = _occurrence_words(child)
    notation = f'<span class="cd-bounds">{escape(_notation(child))}</span>'
    return f"{notation} {escape(words)}" if words else notation


def _occurs_once(child) -> bool:
    """Whether the declaration says what a declaration says when it is silent."""
    return _bounds(child) == (1, 1)


# The schema word carries the row, as it does for a compositor, with the plain
# reading on hover and focus. `minInclusive` is exact and unreadable; "0 or
# greater" is readable and is not what the schema says — so both are here, and
# the one that is the schema's stays in the table.
FACET_GLOSS = {
    "minInclusive": "The value must be this or greater.",
    "maxInclusive": "The value must be this or less.",
    "minExclusive": "The value must be greater than this.",
    "maxExclusive": "The value must be less than this.",
    "pattern": "The value must match this regular expression.",
    "length": "The value must be exactly this long.",
    "minLength": "The value must be at least this long.",
    "maxLength": "The value must be at most this long.",
    "totalDigits": "The value must have at most this many digits in all.",
    "fractionDigits": "The value must have at most this many digits after the point.",
    "whiteSpace": "How whitespace is treated before the value is checked.",
}


UNION_GLOSS = ("A value must be valid against one of these types. Any one of them is enough, and the instance does not say which one was meant.")


def _union_table(union, types) -> str:
    """The members of a union, with what each of them holds.

    A union type carries no values and no facets of its own, so a page built
    from restrictions has nothing to say about it and said nothing — for
    `systemTypeType` neither this tool nor Sandcastle showed more than the word
    `simpleType`. What a reader may write sits one link further on, in the
    members, so the members are what the page carries; the Constraints column
    is the child table's, and says how many values are behind each of them
    before the click.
    """
    if not union:
        return ""
    rows = "".join(
        f"<tr><td>{_type_link(name, types)}</td>"
        f"<td>{_constraints_cell(name, types)}</td></tr>"
        for name in union
    )
    return (
        '<section class="cd-union"><h2>Allowed types '
        '<span class="cd-facet" tabindex="0">union'
        f'<span class="cd-tip" role="note">{escape(UNION_GLOSS)}</span>'
        "</span></h2>"
        + _scrolling("<table><tr><th>Type</th><th>Constraints</th></tr>"
                     + rows + "</table>")
        + "</section>"
    )


def _facet_table(facets) -> str:
    """What narrows the value space, next to the values themselves.

    Sandcastle puts facets and enumeration values in one table; they answer
    different questions — a facet says what a value must satisfy, an
    enumeration says which values there are — and only one of the two carries
    documentation, so they are two tables here.
    """
    if not facets:
        return ""
    rows = []
    for facet in facets:
        name = facet["name"]
        rows.append(
            '<tr><td><span class="cd-facet" tabindex="0">'
            f"{escape(name)}"
            f'<span class="cd-tip" role="note">{escape(FACET_GLOSS.get(name, ""))}</span>'
            f'</span></td><td><code>{escape(facet["value"])}</code></td></tr>'
        )
    return (
        '<section class="cd-facets"><h2>Value constraints</h2>'
        + _scrolling("<table><tr><th>Constraint</th><th>Value</th></tr>"
                     + "".join(rows) + "</table>")
        + "</section>"
    )


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
        '<section class="cd-enumeration"><h2>Allowed values</h2>'
        + _scrolling("<table><tr><th>Value</th><th>Description</th></tr>"
                     + "".join(rows) + "</table>")
        + "</section>"
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


def index_html(types: dict, statistics: dict, meta: dict, has_docs: bool = False) -> str:
    # The slash is the one place a type name may be broken and still read as
    # one name, and the line-breaking algorithm offers no break after it, so
    # the markup marks the opportunity. Where a name has no slash the
    # stylesheet lets it break mid-word instead; without either, 153 of the
    # names are drawn over the column beside them.
    items = "".join(
        f'<li><a href="{TYPES_DIRECTORY}/{escape(slug(name))}/index.html">'
        f'{escape(name).replace("/", "/<wbr>")}</a></li>'
        for name in sorted(types)
    )
    version = meta.get("schemaVersion")
    heading = f"CPACS {escape(version)}" if version else "CPACS schema"
    summary = (
        f'<p class="cd-kind">{statistics.get("types", 0)} types · '
        f'{statistics.get("distinctPaths", 0)} instance paths · '
        f'depth {statistics.get("maxDepth", 0)}</p>'
    )
    docs = (
        f'<p><a href="{DOC_DIRECTORY}/index.html">Documentation</a></p>' if has_docs else ""
    )
    body = f"<h1>{heading}</h1>{summary}{docs}<ul class=\"cd-type-index\">{items}</ul>"
    return _substitute_root(_document(heading, 0, body), depth=0)


def _write_index(output: Path, types: dict, statistics: dict, meta: dict,
                 has_docs: bool = False) -> None:
    (output / "index.html").write_text(
        index_html(types, statistics, meta, has_docs=has_docs), encoding="utf-8"
    )


ASSET_FILES = ("styles.css", "viewer.js")


def asset(name: str) -> str:
    return resources.files(__package__).joinpath("assets", name).read_text(encoding="utf-8")


def _write_assets(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in ASSET_FILES:
        (directory / name).write_text(asset(name), encoding="utf-8")


def router_html() -> str:
    """The single not-found document that serves every tree path.

    Its stylesheet is inlined rather than linked: the page is served from
    arbitrary depth and cannot resolve a relative URL, and it does not know its
    own root until the script has run. The script is inlined for the same
    reason — loading it by absolute URL would need the root first.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>CPACS schema</title>\n"
        f"{THEME_SCRIPT}"
        f"<style>\n{asset('styles.css')}</style>\n"
        '<body class="cd-viewer">\n<div id="cd-app" class="cd-app">\n'
        '<div class="cd-column">\n'
        # The strip is the column's chrome and never leaves: it says which of
        # the column's places is showing, so none of them can read as a layer
        # over another. Search is one of those places rather than a thing that
        # happens to the tree, which is why the field lives inside it. The
        # page's two round buttons keep the strip company at its far end, the
        # row above having gone with the field.
        '<div id="cd-tabs" class="cd-tabs" role="tablist" aria-label="Left column">'
        '<button id="cd-tab-tree" class="cd-tab" type="button" role="tab"'
        ' aria-controls="cd-tree" aria-selected="true">Tree</button>'
        '<button id="cd-tab-docs" class="cd-tab" type="button" role="tab"'
        ' aria-controls="cd-docs" aria-selected="false" tabindex="-1" hidden>Handbook</button>'
        '<button id="cd-tab-search" class="cd-tab" type="button" role="tab"'
        ' aria-controls="cd-search-panel" aria-selected="false" tabindex="-1">Search'
        '<span id="cd-tab-count" class="cd-tab-count"></span></button>'
        '<span class="cd-tabs-rest"></span>'
        f"{THEME_BUTTON}"
        '<button id="cd-help" class="cd-help" type="button" aria-expanded="false"'
        ' title="Keys and query forms" aria-label="Keys and query forms">?</button>'
        "</div>\n"
        # `tabindex="-1"`: a scroll container that carries no tabindex of its
        # own is a tab stop in Firefox 136 and later. One Tab out of the detail
        # panel landed on this pane rather than on the first link inside the
        # panel, and the arrows 0018 gives the panel then moved the tree cursor
        # instead of scrolling what the reader was looking at. Chrome, which
        # exempts a scroller that holds focusable children, never did it. The
        # rows are the tab stops here, and they keep their own tabindex.
        '<div id="cd-tree" class="cd-pane" tabindex="-1"></div>\n'
        # The field is the tab's own content, and the rows scroll under it
        # rather than with it.
        '<div id="cd-search-panel" class="cd-pane cd-search-panel" hidden>'
        '<div class="cd-search">'
        '<input id="cd-search" type="search" placeholder="Search elements, types, attributes"'
        ' autocomplete="off" spellcheck="false" aria-label="Search">'
        '<span id="cd-search-count" class="cd-search-count"></span>'
        "</div>"
        '<div id="cd-results" class="cd-results"></div>'
        "</div>\n"
        '<div id="cd-docs" class="cd-pane" hidden></div>\n'
        "</div>\n"
        '<div id="cd-splitter" class="cd-splitter" role="separator" aria-orientation="vertical"'
        ' tabindex="0" aria-label="Resize the tree pane"></div>\n'
        '<div id="cd-detail" class="cd-pane cd-pane-detail" tabindex="-1"></div>\n'
        "</div>\n"
        f"<script>\n{asset('viewer.js')}</script>\n"
        "</body>\n</html>\n"
    )


def _write_router(output: Path) -> None:
    (output / "404.html").write_text(router_html(), encoding="utf-8")
