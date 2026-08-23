#!/usr/bin/env python3
"""Survey the documentation vocabulary of the CPACS schema.

Reports what a ddue renderer and a media resolver must actually handle, and
which constructs deviate from the pattern the rest of the schema follows.
Nothing here is inferred: every number is counted from the schema and, for the
media section, from the SHFB project file and the file system.

Usage:
    ./survey_doc_vocabulary.py path/to/cpacs_schema.xsd
    ./survey_doc_vocabulary.py path/to/cpacs_schema.xsd --media path/to/documentation

Requires Python 3 and lxml.
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

from lxml import etree

XSD = "http://www.w3.org/2001/XMLSchema"
DDUE = "http://ddue.schemas.microsoft.com/authoring/2003/5"
SD = "http://schemas.xsddoc.codeplex.com/schemaDoc/2009/3"
XLINK = "http://www.w3.org/1999/xlink"

# Documentation on a type is expected as sd:schemaDoc/{summary,remarks}. Any
# other direct child is an outlier the extractor must not silently reinterpret.
EXPECTED_SCHEMADOC_CHILDREN = {"summary", "remarks"}

SHFB_IMAGE = re.compile(r'<Image Include="([^"]+)"\s*>(.*?)</Image>', re.S)
SHFB_ID = re.compile(r"<ImageId>([^<]*)</ImageId>")
SHFB_ALT = re.compile(r"<AlternateText>([^<]*)</AlternateText>")


def q(ns, name):
    return f"{{{ns}}}{name}"


def local(tag):
    return tag.split("}")[-1]


def owning_construct(node):
    """Nearest named XSD construct above a node, e.g. ('complexType', 'wingType')."""
    for ancestor in node.iterancestors():
        if isinstance(ancestor.tag, str) and ancestor.tag.startswith("{" + XSD + "}"):
            if ancestor.get("name"):
                return local(ancestor.tag), ancestor.get("name")
    return None, None


def section(title):
    print(f"\n=== {title} ===")


def survey_vocabulary(root):
    elements = Counter()
    # Attributes are keyed by their qualified name: image/@href and
    # image/@xlink:href are different attributes and must not be merged.
    attributes = Counter()
    parents = defaultdict(Counter)

    for node in root.iter():
        if not isinstance(node.tag, str) or not node.tag.startswith("{" + DDUE + "}"):
            continue
        name = local(node.tag)
        elements[name] += 1
        parent = node.getparent()
        if parent is not None and isinstance(parent.tag, str):
            parents[name][local(parent.tag)] += 1
        for attr in node.attrib:
            if attr.startswith("{"):
                ns, base = attr[1:].split("}")
                shown = f"xlink:{base}" if ns == XLINK else f"{{{ns}}}{base}"
            else:
                shown = attr
            attributes[(name, shown)] += 1

    section(f"ddue elements ({len(elements)} distinct, {sum(elements.values())} total)")
    for name, count in elements.most_common():
        print(f"{count:7d}  ddue:{name}")

    section("ddue attributes")
    for (name, attr), count in sorted(attributes.items(), key=lambda kv: -kv[1]):
        print(f"{count:7d}  ddue:{name}/@{attr}")

    section("attribute value domains")
    for name, attr in sorted({(n, a) for (n, a) in attributes}):
        key = attr if not attr.startswith("xlink:") else q(XLINK, attr.split(":", 1)[1])
        values = Counter(
            e.get(key) for e in root.iter(q(DDUE, name)) if e.get(key) is not None
        )
        if len(values) <= 8:
            print(f"  ddue:{name}/@{attr}: {dict(values.most_common())}")
        else:
            print(f"  ddue:{name}/@{attr}: {len(values)} distinct values")

    section("nesting contexts (element <- parents)")
    for name in sorted(parents):
        print(f"  {name:16s} <- {dict(parents[name].most_common(5))}")

    return elements


def survey_coverage(root):
    section("documentation coverage")

    hosts = Counter()
    for doc in root.iter(q(SD, "schemaDoc")):
        hosts[owning_construct(doc)[0]] += 1
    print("sd:schemaDoc by owning construct:", dict(hosts))

    global_types = {e.get("name") for e in root.findall(q(XSD, "complexType"))}
    documented = {
        owning_construct(d)[1]
        for d in root.iter(q(SD, "schemaDoc"))
        if owning_construct(d)[0] == "complexType"
    }
    undocumented = sorted(global_types - documented)
    print(f"global complexTypes: {len(global_types)} | with sd:schemaDoc: {len(global_types & documented)}")
    print(f"without sd:schemaDoc: {len(undocumented)}")
    for name in undocumented:
        print(f"  {name}")

    section("xsd:documentation (the second, disjoint channel)")
    docs = list(root.iter(q(XSD, "documentation")))
    owners = Counter()
    with_markup = 0
    for doc in docs:
        annotation = doc.getparent()
        owner = annotation.getparent()
        owners[local(owner.tag) if isinstance(owner.tag, str) else "?"] += 1
        if any(isinstance(c.tag, str) and c.tag.startswith("{" + DDUE + "}") for c in doc):
            with_markup += 1
    print(f"total: {len(docs)}")
    print("by owning construct:", dict(owners.most_common()))
    print(f"containing ddue inline markup: {with_markup}")
    both = sum(
        1
        for a in root.iter(q(XSD, "annotation"))
        if a.find(q(XSD, "documentation")) is not None and a.find(q(XSD, "appinfo")) is not None
    )
    print(f"annotations carrying both documentation and appinfo: {both}")


def survey_outliers(root):
    section("structural outliers")
    found = 0
    for doc in root.iter(q(SD, "schemaDoc")):
        children = [local(c.tag) for c in doc if isinstance(c.tag, str)]
        unexpected = set(children) - EXPECTED_SCHEMADOC_CHILDREN
        if unexpected:
            found += 1
            kind, name = owning_construct(doc)
            line = doc.sourceline
            print(f"  {kind} {name!r} (line {line}): children {children}")
    for remarks in root.iter(q(DDUE, "remarks")):
        parent = remarks.getparent()
        if parent is not None and parent.tag != q(SD, "schemaDoc"):
            found += 1
            kind, name = owning_construct(remarks)
            print(f"  {kind} {name!r} (line {remarks.sourceline}): ddue:remarks nested in ddue:{local(parent.tag)}")
    if not found:
        print("  none")


def survey_media(root, media_dir):
    section("media references")

    used = [e.get(q(XLINK, "href")) for e in root.iter(q(DDUE, "image"))]
    distinct = sorted({u for u in used if u})
    print(f"image references: {len(used)} ({len(distinct)} distinct ids)")
    missing_href = sum(1 for u in used if not u)
    if missing_href:
        print(f"  images without xlink:href: {missing_href}")

    if not media_dir:
        print("  (no --media given; catalogue not checked)")
        return

    projects = [f for f in os.listdir(media_dir) if f.endswith(".shfbproj")]
    if not projects:
        print(f"  no .shfbproj found in {media_dir}")
        return
    project = os.path.join(media_dir, projects[0])
    text = open(project, encoding="utf-8-sig").read()

    catalogue = {}
    alt_text = {}
    for path, body in SHFB_IMAGE.findall(text):
        image_id = SHFB_ID.search(body)
        if not image_id:
            continue
        catalogue[image_id.group(1)] = path.replace("\\", "/")
        alt = SHFB_ALT.search(body)
        if alt:
            alt_text[image_id.group(1)] = alt.group(1)

    print(f"catalogue: {os.path.basename(project)} | entries: {len(catalogue)} | with AlternateText: {len(alt_text)}")

    unresolvable = sorted(set(distinct) - set(catalogue))
    print(f"referenced but not in catalogue: {len(unresolvable)}")
    for name in unresolvable:
        print(f"  {name}")

    unused = sorted(set(catalogue) - set(distinct))
    print(f"catalogued but unreferenced: {len(unused)}")
    for name in unused:
        print(f"  {name}")

    mismatched = [
        (i, p) for i, p in catalogue.items()
        if os.path.splitext(os.path.basename(p))[0] != i
    ]
    print(f"id differs from filename stem: {len(mismatched)}")
    for image_id, path in sorted(mismatched):
        print(f"  {image_id} -> {path}")

    absent = [(i, p) for i, p in catalogue.items() if not os.path.exists(os.path.join(media_dir, p))]
    print(f"catalogued but absent on disk: {len(absent)}")
    for image_id, path in sorted(absent):
        flag = " (referenced)" if image_id in distinct else ""
        print(f"  {image_id} -> {path}{flag}")

    extensions = Counter(os.path.splitext(p)[1] for p in catalogue.values())
    print("extensions:", dict(extensions.most_common()))
    collisions = Counter(e.lower() for e in extensions)
    for ext, count in collisions.items():
        variants = [e for e in extensions if e.lower() == ext]
        if len(variants) > 1:
            print(f"  case variants for {ext}: {variants}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("schema", help="path to cpacs_schema.xsd")
    parser.add_argument("--media", help="path to the documentation directory holding the .shfbproj and figures")
    args = parser.parse_args()

    if not os.path.exists(args.schema):
        print(f"no such file: {args.schema}", file=sys.stderr)
        return 2

    root = etree.parse(args.schema).getroot()
    print(f"schema: {args.schema}")
    print("namespaces:", {k: v for k, v in root.nsmap.items()})

    survey_vocabulary(root)
    survey_coverage(root)
    survey_outliers(root)
    survey_media(root, args.media)
    return 0


if __name__ == "__main__":
    sys.exit(main())
