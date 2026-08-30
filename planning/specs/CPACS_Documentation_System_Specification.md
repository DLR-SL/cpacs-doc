# Specification: New CPACS Documentation System

**Status:** Draft · **Issued:** 2026-08-22 08:37 CEST · **Subject:** `DLR-SL/CPACS`, branch `develop`, schema v3.5.1-RC

---

## 1. Situation

Two tools currently cover complementary parts of the need, and neither covers it fully.

**XSDDiagram** provides navigation: fast traversal of the element tree by keyboard or mouse, types toggled on and off, an attribute table. It reads only `xsd:documentation` — `DiagramHelpers.GetAnnotationText()` handles nothing but `XMLSchema.documentation`, so `xsd:appinfo` falls through — and it does not resolve type references. It is also desktop-only, built on .NET 2.0 and WinForms. The last commit on the default branch of `dgis/xsddiagram` is dated **2019-12-17**; the project has been unchanged for over six years.

**Sandcastle/SHFB with the XsdDocumentationPlugin** provides content: the full `sd:schemaDoc`/`ddue` block is rendered to HTML. In exchange, navigation is type-centric rather than tree-centric, output files carry GUID names (`NamingMethod: Guid`), and the toolchain depends on a Windows runner, MSBuild, .NET Framework 3.5, HTML Help 1 (`hhc.exe`), and a 46 MB binary blob (`development/3rdparty.zip`) containing a plugin unchanged since 2015 from the defunct CodePlex ecosystem.

### 1.1 Schema measurements

All requirements below rest on these figures, taken from `schema/cpacs_schema.xsd`, 43,602 lines, v3.5.1-RC.

All figures below are measured against DLR-SL/CPACS, branch `develop`, commit `45a6e61` (2026-08-23), using `tools/survey_doc_vocabulary.py` and `cpacs-doc report`. Earlier editions of this table carried different figures; the values here supersede them. Four schema defects found during phase 1 have since been fixed at the source, which is why some counts differ from the original survey.

#### Size and documentation coverage

| Metric | Value | Consequence |
|---|---|---|
| Global complexTypes | 1,101 | Type index as its own navigation dimension |
| complexTypes carrying `sd:schemaDoc` | 1,079 (98 %) | Content sits almost entirely on the type |
| complexTypes without documentation of either kind | 16 | Build report material, not an extractor concern |
| complexTypes documented via `xsd:documentation` instead | 6 | The two channels are not cleanly separated |
| Global simpleTypes | 8 | |
| Element declarations | 3,631 | |
| of those with `@type` | 3,543 (97.6 %) | Type resolution is the norm, not the exception |
| Elements carrying `sd:schemaDoc` | 5 | Tree nodes are substantively empty |
| simpleTypes carrying `sd:schemaDoc` | 5 | Documentation is not confined to complexTypes |
| Elements with `xsd:documentation` | 1,978 | One-liners, complementary to the type documentation |
| `xsd:documentation` total | 2,091 | Also on enumerations, attributes and compositors |
| `xsd:annotation` total | 3,177 | |
| `xsd:appinfo` total | 1,089 | used exclusively for `sd:schemaDoc` |
| Distinct `ddue` element types in use | **25** | Renderer scope is tractable |
| Attribute declarations | 311 | |
| `xsd:enumeration` | 265 | Value lists belong on the detail page |

#### Instance tree structure

| Metric | Value | Consequence |
|---|---|---|
| Expanded instance tree (nodes) | **54,552** | Pre-rendering the whole tree is not possible |
| Distinct instance paths | **53,692** | 53,692 HTML pages cannot be shipped → §3.4 |
| Paths reachable through several `choice` branches | 860 | One URL, two readings of cardinality → §6 |
| Maximum tree depth | 22 | |
| Average path length | 148 characters | |
| Cycles in the type graph | **0** | Tree construction terminates without cycle detection |
| `xsd:complexContent/extension` | 1,080 | Inheritance must be shown |
| of those based on `complexBaseType` | 1,051 | Inheritance is flat and uniform (max depth 2) |

#### Compositors

| Metric | Value |
|---|---|
| `xsd:all` / `sequence` / `choice` (compositors) | 509 / 604 / 84 |
| Element declarations **inside** `all` / `sequence` / `choice` | **2,462 / 1,004 / 164** |

Weighted by element, more than two thirds of all child elements sit inside an order-free `all`. Classifying the 604 `sequence` compositors by cause:

| Cause | Count | Share |
|---|---|---|
| A child has `maxOccurs > 1` (forbidden inside `xsd:all` in XSD 1.0) | 469 | 77.6 % |
| Nested compositor (forbidden inside `xsd:all`) | 57 | 9.4 % |
| Both repetition and nesting | 2 | 0.3 % |
| At most one child — order is meaningless | 10 | 1.7 % |
| More than one child, **no technical reason apparent** | **66** | 10.9 % |

In roughly 88 % of cases the enforced order is a technical artefact of the XSD 1.0 rules, not a statement of intent. Not a single `all` child in the schema carries `maxOccurs > 1`; the restriction applies without exception. The 66 cases in the last category form a review list for schema maintenance.

#### Cardinalities

| Cardinality | Count |
|---|---|
| `0..1` optional | 1,642 |
| `1..1` mandatory | 1,510 |
| `1..unbounded` | 349 |
| `0..unbounded` | 110 |
| `2..unbounded` | 14 |
| `0..2` / `1..2` / `3..unbounded` | 2 / 2 / 2 |

| Metric | Value | Consequence |
|---|---|---|
| Elements **without** a `minOccurs` attribute (default = mandatory) | 1,861 | Mandatory status is invisible in the source |
| Elements without a `maxOccurs` attribute | 3,152 | |
| Tree nodes: mandatory element under an optional ancestor | **20,482 of 54,065 (38 %)** | "Mandatory" without path context misleads → S4 |

#### uID references (inventory; not evaluated in v1)

| Metric | Value |
|---|---|
| Types carrying a `uID` attribute (own or inherited) | 226 |
| `uID` attribute declarations | 243 |
| Distinct element names declaring a uID carrier | 395 |
| Elements of type `stringUIDBaseType` (references) | **340** |
| of those, distinct names | 193 |
| Reference elements **with** `xsd:documentation` | 227 of 340 |
| Reference elements **without** any documentation | **113** |
| Tautological descriptions (`wingUID` → "Reference to a wing uID") | 18 |
| Names breaking the `…UID` convention | 9 |

The nine outliers are `positionXUidEnd`, `-Max`, `-Mid`, `-Min`, `-Start` (spelled `Uid`, and not at the end of the name), plus `mCargo`, `mPax`, `operatingAirline`, and `uID` itself. They constitute a finding for schema maintenance in their own right.

### 1.2 Core findings

1. **The split between structure (element) and content (type) is a schema convention, not a tooling defect.** A new system must bring the two together at display time instead of choosing a side.
2. **`ddue` is semantic markup, not HTML.** The documentation content is transformable without loss. This is a transformation problem, not a re-authoring problem.
3. **The structural semantics of the schema are systematically invisible in the source.** Mandatory status by absence of an attribute, order-freedom by a compositor name, conditional obligation not at all. This explains recurring user errors and is derivable from the schema without additional information.

---

## 2. Goals and non-goals

### 2.1 Goals

- **G1 — Navigation and content unified.** The user moves through the instance tree and sees the full documentation of the referenced type while doing so.
- **G2 — Web-based, locally operable.** Static output for GitHub Pages, plus a local mode for schema development (§3.5). For the limits of pure file-system operation see N6.
- **G3 — Stable, meaningful, linkable URLs.** Citable in papers, issues, and tool manuals. The **type pages are the canonical citable layer**: they are real files answering with HTTP 200. Tree paths are navigation state and carry HTTP 404 by construction (§3.4).
- **G4 — Reproducible build without proprietary dependencies.** Linux CI, no binary blobs in the repository, no end-of-life components.
- **G5 — The schema remains the single source of truth.** No parallel documentation source, no registration obligations outside the XSD.
- **G6 — Extensible to toolspecific schemas and to multiple schema versions.**
- **G7 — Make structural semantics visible.** Compositor and cardinality rules are presented so that they are understood without a legend (§6).

### 2.2 Non-goals for v1

- No schema editor. Read access only.
- No validation of instance documents; that remains with `cpacs-schema-tool` and TiXI.
- No server-side component. No backend, no database.
- **No derivation of uID links.** Neither heuristically nor through curated lists. See §10.
- No support for arbitrary XSD across the full language. The subset actually used in CPACS governs (see §1.1); unsupported constructs are detected and reported, never silently ignored.
- No CHM output.
- No fork of XSDDiagram (§12, E5).

---

## 3. Architecture

Three decoupled stages with a documented interchange format between them.

```
schema/cpacs_schema.xsd
        │
        ▼
  [1] Extractor  (Python 3, lxml)
        │  cpacs-doc-model.json  ← stable, versioned intermediate format
        ▼
  [2] Generator  (static site builder)
        │  HTML (type pages only) + JSON chunks + search index
        ▼
  [3] Viewer     (browser: tree canvas + detail panel)
```

Decoupling through a persisted intermediate model is the single most important design decision. It allows the viewer to be replaced or supplemented without touching the extractor, and it turns the model itself into a usable artefact for third-party tools such as TiGL code generators or diff utilities.

### 3.1 Stage 1 — Extractor

**Input:** one or more XSD files.
**Output:** `cpacs-doc-model.json`, possibly split (see §4.3).

Tasks:

1. Parse the XSD, resolving `include` and `import`.
2. Build the type catalogue (complexType, simpleType) including inheritance resolution for `complexContent/extension`: inherited attributes and particles are marked as inherited, not copied.
3. Build the instance tree from the global root element `cpacs` of type `cpacsType`.
4. Link every tree node to its type.
5. Extract and normalise annotations (see §5).
6. Derive structural semantics: compositor kind, declared and effective cardinality, classification of enforced ordering (see §6).
7. Run consistency checks and set an exit code (see §8.3).

The extractor is **pure**: no network access, no layout decisions, no HTML generation.

**Independence.** The extractor has **no dependency on `cpacs-schema-tool`** (E4). That tool serves solely as a reference for proven solutions. Two things are adopted by imitation rather than by import:

- the parser settings (`no_network=True`, `strip_cdata=False`, no entity resolution, comments preserved), so that linter and extractor see the same schema;
- the shape of a diagnostic message (`code`, `severity`, `message`, `line`, `xpath`), so that reports from both tools look alike.

The writing half of that reference — attribute ordering, serialisation, atomic writes, policy resolution, rename planning — is not needed, since the extractor only reads.

### 3.2 Stage 2 — Generator

From the model it produces:

- one HTML page **per type** (1,101 pages, see §3.4),
- `404.html` as the router for tree paths,
- JSON chunks for the lazily loaded tree fragments,
- the client-side search index,
- asset copies (figures, equations),
- the redirect map for legacy Sandcastle GUID URLs.

### 3.3 Stage 3 — Viewer

A two-part layout:

- **left**, the navigable tree canvas — what XSDDiagram does well;
- **right**, the detail panel with rendered type documentation, attributes, child elements, and enumerations.

### 3.4 Rendering strategy

**Requirement R1 (E1):** Only the **1,101 type pages** are pre-rendered. Tree paths get no physical file.

The reason is an order of magnitude: 53,692 distinct instance paths at roughly 15 kB per page would amount to about 800 MB across 53,000 files — beyond what GitHub Pages sensibly carries.

**Requirement R2:** Tree paths are resolved client-side. A request for `/tree/vehicles/aircraft/model/fuselages/fuselage/` matches no file, so GitHub Pages serves `404.html` **while keeping the requested address in the browser's address bar**. `404.html` is not an error page but the viewer itself: it reads the path from the address bar, looks up the corresponding type in the model, expands the tree, and displays the documentation. The URL is unchanged, copyable, and citable.

**Requirement R3 — degradation without JavaScript.** Without JavaScript the address bar cannot be evaluated. `404.html` therefore also carries a static notice linking to the type index. What is lost in that mode is bounded: the breadcrumb, the cardinality at the specific insertion point, and the element one-liner. The documentation content itself is not lost, because it sits on the type in 98 % of cases and is fully pre-rendered on the type page.

**Measured on GitHub Pages** (public project site, `DLR-SL/spike-routing`, Phase 0 spike 1). R2 holds: the requested address is preserved, no redirect occurs, and path length is not a constraint — 266 characters across 22 segments route identically to a short path. Three properties constrain the implementation:

- **One not-found document serves the entire site.** A `404.html` placed in a subdirectory is ignored. The router therefore cannot infer the schema version from its own location: it parses the version from the requested path, knows which versions exist, and handles a leading segment naming a version that does not.
- **Asset references must be absolute**, with the deployment prefix as a build-time parameter (N18). `404.html` is served from arbitrary depth, so a relative URL resolves against the requested path rather than the file's location. The failure is silent: a misdirected request receives the router page as a valid HTML response, and `fetch()` does not reject on HTTP 404. Every `fetch()` therefore checks `response.ok` before touching the body, and the router does not answer as a router for paths ending in an asset extension.
- **Tree paths carry HTTP status 404.** Invisible in the browser, but link checkers report dead links, reference managers fail to resolve, archiving services skip the URL, and search engines do not index it. This is a limitation of G3, not a reason to reopen E1 — the alternatives below remain worse — and it is why type pages are the canonical citable layer.

**Rejected:**

- Pre-rendering all paths — not shippable.
- Pre-rendering down to a depth limit — 6,260 extra pages (~90 MB) through depth 8, already 19,021 pages (~285 MB) through depth 10. Feasible, but the limit is arbitrary and cannot be explained to a user: a path at depth 9 would behave differently from one at depth 8. Under R1/R2 the rule is uniform.

### 3.5 Operating modes

Measured timings on the full schema (`cpacs-doc report`, 2026-08): 1.5 s end to end, of which tree construction over 54,552 nodes dominates; writing the model adds 0.6 s. The model is built in about two seconds. Two local operating modes follow from this.

```
cpacs-doc serve schema/cpacs_schema.xsd            # development mode
cpacs-doc build schema/cpacs_schema.xsd -o site/   # what CI does
```

**Requirement R4 — `serve`.** Starts a local HTTP server, builds the model in memory, serves the viewer assets, and watches the input file. On save in the editor the model is rebuilt and the browser refreshes. **No pre-rendering**, no output files on disk — the viewer needs only the model; pre-rendering exists solely for deployment.

The server reproduces the not-found behaviour of the deployment target: requests without a matching file are routed to the viewer, and directory listings are suppressed. Neither is default behaviour in Python's `http.server`, which answers a directory without `index.html` with a generated listing and never serves a custom not-found document. Without this, development mode diverges from what is published in exactly the way that no later test would catch.

The build report (N10) runs on every rebuild and writes to the terminal. Schema authoring thus gets immediate feedback on undocumented types, unknown `ddue` elements, unresolvable figure IDs, `sequence` compositors without a technical reason, and reference elements without documentation.

**Requirement R5 — `build`.** Produces the complete deployment directory. Needed locally only to check what CI will produce.

**Requirement R6 — arbitrary XSD.** Both modes accept any XSD file from the file system, including uncommitted files and files outside CPACS. This covers the use case XSDDiagram serves today (§12, E5). For schemas without `sd:schemaDoc`, fallback chain A1 falls back to `xsd:documentation`.

**Rejected:** a pure browser viewer with drag-and-drop of an XSD file and extraction in JavaScript. Convenient and usable without a Python installation, but it would mean writing the extractor a second time in a second language and keeping the two in permanent sync.

---

## 4. Data model

### 4.1 Top-level structure

```jsonc
{
  "meta":  { "schemaVersion": "3.5.1-RC", "modelVersion": "1.0",
             "generated": "2026-08-22T...", "sourceHash": "sha256:..." },
  "types": { "<typeName>": TypeNode },
  "tree":  TreeNode           // root: cpacs
}
```

### 4.2 TypeNode and TreeNode

```jsonc
TypeNode = {
  "name": "fuselageType",
  "kind": "complex" | "simple",
  "base": "complexBaseType" | null,
  "abstract": false,
  "doc": DocBlock,                        // see §5
  "attributes": [ { "name", "type", "use", "default", "doc",
                    "inheritedFrom": "complexBaseType" | null } ],
  "content": Compositor | null,
  "enumeration": [ { "value", "doc" } ] | null,
  "simpleContentBase": "xsd:string" | null,
  "usedBy": [ "<typeName>", ... ],        // back-reference: which types use this one
  "sourceLine": 12345
}

Compositor = {
  "kind": "sequence" | "all" | "choice",
  "orderRelevance": "free"                // kind = all
                  | "forced-repetition"   // sequence due to maxOccurs > 1
                  | "forced-nesting"      // sequence due to a nested compositor
                  | "irrelevant"          // at most one child
                  | "declared",           // sequence with no technical reason
  "items": [ ElementRef | Compositor ]
}

ElementRef = {
  "name": "fuselage",
  "type": "fuselageType",
  "minOccurs": 0, "maxOccurs": "unbounded",
  "minOccursExplicit": true,              // false = default 1, invisible in the source
  "doc": DocBlock | null,                 // element-level one-liner, if present
  "sourceLine": 12350
}

TreeNode = {
  "name": "fuselage",
  "path": "/cpacs/vehicles/aircraft/model/fuselages/fuselage",
  "type": "fuselageType",
  "minOccurs": 0, "maxOccurs": "unbounded",
  "compositor": "sequence",               // compositor of the parent
  "orderRelevance": "forced-repetition",  // inherited from the parent compositor
  "effectiveRequirement": "mandatory"            // mandatory unconditionally
                        | "conditional"          // mandatory if the ancestor is present
                        | "optional",
  "conditionalOn": "/cpacs/vehicles/aircraft",   // only when "conditional"
  "hasChildren": true,
  "childCount": 7,
  "children": [ TreeNode ] | null         // null = load on demand, see §4.3
}
```

**Requirement D1:** The tree is not materialised redundantly. Since 3,543 of 3,631 elements are typed and many types occur repeatedly, `children` is filled inline only where the chunk budget allows; otherwise it is loaded via `type`. The 54,552-node tree comes into being client-side and only along the paths actually expanded.

**Requirement D2:** Inherited attributes and particles appear in the model with `inheritedFrom`. The viewer shows them by default, visually set apart, and allows hiding them. With 1,051 types based on `complexBaseType`, a bare link to the base type would be user-hostile.

### 4.3 Chunking

**Requirement D3:** No client loads more than 250 kB (uncompressed) for the initial state. Split as follows:

- `index.json` — meta, list of type names, root tree to depth 3
- `types/<name>.json` — one chunk per type, on demand
- `search-index.json` — separate, loaded lazily on first focus of the search field

Shipped with pre-compressed `.gz`/`.br` sidecars, since GitHub Pages does not compress on the fly.

### 4.4 URL scheme

**Requirement D4:** URLs are path-based, case-sensitive like the schema, and stable across schema versions for as long as the path exists.

```
/v3.5.1/tree/vehicles/aircraft/model/fuselages/fuselage/    → resolved via 404.html
/v3.5.1/type/fuselageType/                                  → pre-rendered file
/v3.5.1/type/fuselageType/#attributes
/v3.5.1/search?q=...
/latest/...                    → alias for the current stable version
```

Explicitly **not** GUID-based. A redirect table from the legacy Sandcastle GUID URLs to the new paths is generated once during the first build and shipped as a static redirect map, so that existing links in papers and issues do not break.

---

## 5. Documentation vocabulary

### 5.1 Normalised DocBlock

```jsonc
DocBlock = {
  "summary": [ Inline | Block ],   // from ddue:summary or xsd:documentation
  "remarks": [ Block ],            // from ddue:remarks
  "sections": [ { "title": "...", "content": [ Block ] } ],
  "source": "schemaDoc" | "documentation" | "inherited" | null
}
```

**Requirement A1 — fallback chain.** For a tree node the DocBlock is determined in this order:

1. `sd:schemaDoc` on the element (5 cases),
2. `xsd:documentation` on the element (1,982 cases), as `summary`,
3. `sd:schemaDoc` on the referenced type (1,079 types), as `summary` plus `remarks`,
4. `sd:schemaDoc` on the base type, where the type itself is undocumented.

Steps 2 and 3 are **combined**, not treated as alternatives: the element one-liner is the context-specific short description, the type documentation the general part. The viewer marks the provenance. This combination is precisely what both legacy tools lack — Sandcastle uses type documentation only as a *substitute*, via `useTypeDocumentation forUndocumentedElements`.

### 5.2 ddue renderer

**Requirement A2:** The 26 `ddue` elements actually in use map to HTML as follows:

| ddue | HTML | Occurrences |
|---|---|---|
| `para` | `<p>` | 2436 |
| `summary`, `remarks`, `content` | container | 1089 / 993 / 343 |
| `list`, `listItem` | `<ul>/<ol>`, `<li>` | 77 / 384 |
| `table`, `row`, `entry` | `<table>`, `<tr>`, `<td>` | 13 / 55 / 188 |
| `section`, `title` | `<section>`, `<h3>` | 60 / 62 |
| `code` | `<pre><code>` with `@language` | 50 |
| `codeInline` | `<code>` | 256 |
| `legacyBold`, `legacyItalic`, `emphasis` | `<strong>`, `<em>` | 103 / 306 / 3 |
| `externalLink` (`linkText`/`linkUri`) | `<a rel="noopener">` | 8 |
| `mediaLink`, `image` | `<figure><img>` | 116 / 116 |
| `definitionTable`, `definedTerm`, `definition` | `<dl>`, `<dt>`, `<dd>` | 1 / 2 / 2 |
| `superscript` | `<sup>` | 2 |
| `math` | MathML/KaTeX | 1 |

Unknown `ddue` elements raise a warning in the build report and are passed through as plain text — never silently discarded.

### 5.3 Vocabulary decision (E7)

The schema uses `sd:schemaDoc` in the namespace `http://schemas.xsddoc.codeplex.com/schemaDoc/2009/3` and `ddue` in the Microsoft authoring namespace. Both originating projects are discontinued.

**Decision:** the vocabulary stays **unchanged** in v1. Rationale: 1,079 documented types and 2,436 `para` elements would make for an enormous, purely mechanical schema diff with no substantive benefit, and it would collide with any schema development in flight. Instead, the subset in use is **frozen and described normatively** in a document of its own, "CPACS Documentation Vocabulary". The namespace URIs thereby become mere identifiers, with no dependency on the dead originating projects.

A later move to a CPACS-owned documentation namespace remains possible and is then a pure XSLT rename, bridged on the extractor side by accepting both namespaces.

### 5.4 Figures

**Requirement A3 — convention over registration.** Today every figure must be entered as an `<Image ItemGroup>` with an `ImageId` in `Cpacs_doc_project.shfbproj`, and the schema references it by `xlink:href` against that ID. That is 116 references, a hard coupling between schema and build project file, and a silent failure mode on typos.

New behaviour: `<ddue:image xlink:href="basicPrinciple"/>` is resolved against `documentation/figures/` and `documentation/svgs/`, with the file name minus extension serving as the ID and SVG preferred over raster. No project-file entries. Unresolvable IDs and unused files both appear in the build report.

---

## 6. Making structural semantics visible

This section collects the requirements that follow from finding 3 in §1.2. They address a documented user pain point: incorrectly ordered data sets and misread obligation, without users understanding why.

### 6.1 Compositors

**Requirement S1:** The presentation of the child list carries the rule itself, not merely a symbol:

- **`all`** — children sorted alphabetically, **unnumbered**, with a prominently visible note that order is free.
- **`sequence`** — children in schema order, **numbered**. The numbering carries real information: the required position.
- **`choice`** — children indented under a line reading "exactly one of".

Plus the compositor symbol on the parent node, as in XSDDiagram, because users are accustomed to it. The marking must be **conspicuous rather than discreet**: with 2,462 elements inside `all` against 1,004 inside `sequence`, the distinction is not a marginal detail.

The deciding argument: the same numbering that is informative under `sequence` would create a false expectation under `all`. A user who sees an alphabetical, unnumbered list has understood the rule without reading a legend.

### 6.2 Classification of enforced ordering

**Requirement S2:** For `sequence`, the viewer states **why** the order is fixed, following `Compositor.orderRelevance`:

- *technically enforced* — a child repeats (`maxOccurs > 1`) or a nested compositor is present; XSD 1.0 disallows `xsd:all` in both cases. 528 of 604 cases.
- *no technical reason apparent* — 66 cases. This list also enters the build report as a review list for schema maintenance.

The question "why must this be in this order" thus gets an answer for the first time. The classification is derivable in full from the schema; the XSD 1.0 rules are unambiguous and no heuristic is involved.

### 6.3 Cardinality

**Requirement S3 — explicit cardinality.** Cardinality is always spelled out, never implied by absence. Plain language rather than notation: "exactly once", "optional, at most once", "at least once, any number of times". The 20 exotic cases (`2..unbounded`, `0..2`, `1..2`, `3..unbounded`) get their figures written out.

Rationale: 1,861 elements carry no `minOccurs` attribute and are therefore mandatory by default. A reader of the XSD sees absence and infers optionality.

**Requirement S4 — effective cardinality in path context.** The tree node additionally shows the effective requirement. A `1..1` element under an optional ancestor appears as "mandatory if *&lt;ancestor&gt;* is present", linking to the ancestor that imposes the condition.

Rationale: 20,482 of 54,065 tree nodes (38 %) are mandatory elements beneath an optional ancestor. A user reading "mandatory" on a detail page without the path context draws the wrong conclusion.

The type page, which has no path context, shows only the declared cardinality together with a note to that effect. S4 is purely computational from the tree and is one of the points where the new system does something neither XSDDiagram nor Sandcastle could, because both lack path context.

---

## 7. Functional requirements of the viewer

### 7.1 Tree navigation

- **F1** Keyboard navigation: arrow keys (up/down for siblings, left/right to collapse and expand), Home/End, Enter to focus the detail panel. Modelled on XSDDiagram, since the behaviour is already learned.
- **F2** Types toggled on and off at the node, persisted in `localStorage`.
- **F3** Cardinality and compositor are visible at the node. For the detailed treatment see §6 (S1–S4).
- **F4** Globally adjustable expansion depth, analogous to XSDDiagram's `-e N`.
- **F5** The current path is always visible as a breadcrumb and copyable as an XPath. A copy button yields the TiXI-compatible path.

### 7.2 Detail panel

- **F6** Full rendered type documentation (`summary`, `remarks`, `sections`) plus the element one-liner, with provenance marked.
- **F7** Attribute table with name, type, use, default, description, and inheritance origin.
- **F8** Child elements as a linked table with type and cardinality, presented according to S1.
- **F9** Enumeration values in full, with descriptions where documented (265 values in the schema).
- **F10** "Used by" — the list of types and paths that incorporate this type.
- **F11** Link to the schema source: a permalink to file and line number, from `sourceLine`. The URL pattern is a configurable template, not hard-wired to one forge — GitHub uses `/blob/<sha>/<file>#L<n>`, GitLab `/-/blob/<sha>/<file>#L<n>`. See N18.

### 7.3 Search

- **F12** Client-side full-text search across element, type and attribute names, and `summary` text. Instance paths are searched where the query is one, which is the form carrying a slash — every descendant of a `wingCutOut` has that name in its own path, so reading paths on every query answered `wingCutOut` with `eta`, `xsi` and the rest of what stands under one (amended 2026-08-30). No backend. Unaffected by the deferral of the reference graph: searching for `wingUID` and getting the occurrences is full-text search, not derivation.
- **F13** Ranking: exact element or type name, before a name the query opens, before a name containing it, before body text. A path query ranks by path, the shortest first (amended 2026-08-30: a path segment no longer ranks in a query that is not a path).
- **F14** Results navigate directly into the tree, expanding the path. Search is a place in the left column rather than something that happens to the tree: it holds a tab of its own, and opening a result leaves the query standing to come back to. See decision 0013.

### 7.4 Diagram export

- **F15** Export of the currently visible tree section as SVG. Preserves the value XSDDiagram has for papers and presentations.
- **F16** Headless generation of the same export via CLI, for use in publications and reports.

### 7.5 Versioning and diff

- **F17** Multiple schema versions available in parallel under `/v<version>/`, with a version switcher that retains the current path where it exists in the target version. The repository holds 16 tags, 9 of them stable releases from v2.3 onward; realistically the eight releases from v3.0 are relevant.
- **F18** Diff view, **stage α in v1** (E3): a set comparison of two model files over paths and type names — what is new, what is gone. This answers the question that arises most often in practice: a tool breaks after a version change and the vanished path must be found. Derived from the model, not from an XSD text diff.
  - **Stage β (v2):** changes within a type — attributes, cardinalities, compositor, enumeration values. Deliberately deferred until `meta.modelVersion` is stable; otherwise the model's own versioning produces phantom changes.
  - **Stage γ:** rejected. A text diff of the documentation produces mostly noise across 2,436 `para` elements; anyone looking for description changes is better served by the GitHub diff, which F11 links to anyway.
  - **Renames** are not detected automatically — that would be a heuristic again. A renamed type appears as "removed" plus "added". Where the release process maintains a machine-readable mapping, the diff view can read it; otherwise it honestly shows two separate entries.

---

## 8. Non-functional requirements

### 8.1 Build

- **N1** Complete build on a standard Linux runner. No Windows runner, no MSBuild, no `hhc.exe`. The CI description is forge-specific and therefore configuration, not architecture; the requirement is the Linux-only build.
- **N2** No binary artefacts in the repository. `development/3rdparty.zip` (46 MB) is dropped outright; all dependencies come through `pixi` or the package manager of the viewer stage.
- **N3** *(non-binding)* Orientation figure for build duration: under 3 minutes. Uncritical given the measurements in §3.5 — model generation takes under a second, and duration is dominated by pre-rendering the 1,101 type pages.
- **N4** The build is deterministic: identical schema input yields byte-identical output. The one relevant exception is the timestamp in `meta`, which must be fixable through an environment variable.
- **N5** Local build with a single command, without network access after dependency setup.

### 8.2 Delivery

- **N6** Purely static output, running on GitHub Pages. **Qualification regarding file-system operation:** browsers block `fetch()` on `file://` URLs. Concretely:
  - the 1,101 pre-rendered type pages are readable by double-click, because their content is in the HTML;
  - tree navigation and search require `cpacs-doc serve`. A generic static server does not suffice: `python -m http.server` never serves a custom not-found document, so tree paths fail there even over HTTP (R4).

  Embedding the model into every page to achieve full `file://` operation fails on size.
- **N7** Pre-compressed `.gz`/`.br` sidecars for all text artefacts.
- **N8** Footer with imprint, privacy, terms of use, and accessibility as a **template component**, not as after-the-fact regex patching; `Cpacs_doc_dsgvo.py` is dropped.
- **N9** No third-party resources at runtime. All fonts, scripts, and styles ship with the site — a data-protection consideration as much as a technical one.

### 8.3 Quality assurance

- **N10** The extractor emits a build report. Diagnostic categories:
  - undocumented types,
  - undocumented elements whose type is also undocumented,
  - **reference elements (`stringUIDBaseType`) without documentation** — currently 113 of 340,
  - unknown `ddue` elements,
  - unresolvable figure IDs,
  - unused figure files,
  - **`sequence` compositors with no apparent technical reason** — currently 66,
  - unsupported XSD constructs.
- **N11** Configurable thresholds fail the CI job when coverage regresses. Baselines from the current state: 98 % of complexTypes documented; 227 of 340 reference elements documented.
- **N12** Golden-file tests: for a representative set of types — at minimum `fuselageType`, `wingType`, `fuelTankType`, `vesselType`, `transformationSE3Type`, `complexBaseType` — the model output is checked against committed reference files.
- **N13** Accessibility: full keyboard operation, contrast ratios per WCAG 2.1 AA, semantic HTML with ARIA roles for the tree.

### 8.4 Maintainability

- **N14** No component without active upstream maintenance. Selection criterion: a release within the last 12 months.
- **N15** The intermediate format is versioned via `meta.modelVersion` and documented. Breaking changes increment the major version.
- **N16** The extractor is usable independently of the viewer and is provided as a standalone package, **without a dependency on `cpacs-schema-tool`** (E4). Dependencies: Python 3 and `lxml`.
- **N17** Parser settings match those of `cpacs-schema-tool` (`no_network=True`, `strip_cdata=False`, no entity resolution), so that both tools see the same schema. Imitation, not coupling.
- **N18 — forge independence.** The solution depends on no capability unique to one hosting platform. Three touch points exist and are all configuration rather than architecture:
  - **Not-found routing (R2).** Both GitHub Pages and GitLab Pages serve a custom `404.html`. **Verified on GitHub Pages** (§3.4); there, resolution is site-wide and a `404.html` in a subdirectory has no effect. The per-directory resolution documented for GitLab project pages under `/project-slug/` is **not verified** — it would be an additional capability, and the router must not depend on it. The deployment prefix differs per target and is a build-time parameter, not a hard-wired value. One caveat applies to access-controlled deployments: a not-found path may redirect to sign-in instead of serving the custom page. Any deployment target must therefore be verified once before it is relied upon.
  - **Source links (F11).** URL pattern as a configurable template.
  - **CI description and runner naming (N1).** Forge-specific file, identical requirements.

  Unaffected: pre-compressed sidecars (N7) are required on both platforms, since neither compresses on the fly. The GUID redirect map is relevant only to the public deployment and remains a build option.

---

## 9. Extension to toolspecific

**Requirement T1:** `schema/toolspecific_template.xsd` and arbitrary tool schemas are processed by the same pipeline. The extractor accepts multiple input schemas and produces separate models with optional cross-linking into the core CPACS model.

`Toolspecific_doc_project.shfbproj` thereby disappears as a separately maintained project file; tool operators instead configure a declarative file — schema path, title, output path — without needing MSBuild knowledge. For the ad-hoc case, `cpacs-doc serve <file>.xsd` suffices (R6).

---

## 10. Deferred: the uID reference graph

**Decision (E2): v1 derives no uID links** — neither heuristically nor from a curated exception list. The user is oriented by the description text next to the referencing element.

### 10.1 Rationale

Derivation from element names was tested and rejected. Measurements:

| Method | Hit rate |
|---|---|
| Name stem + `Type` (`sectionUID` → `sectionType`) | 42 of 193 (22 %) |
| Name stem against uID-bearing element names, longest suffix match | 114 of 193 (59 %), **0 ambiguities** |

Even the better method leaves 79 names open and is fundamentally exposed to collisions and ambiguities that may arise at fleet level or through future schema extensions. Documentation that presents a guess as a fact is worse than documentation that stays silent.

### 10.2 The underlying finding

CPACS has a reference mechanism but **no way to name the target of a reference in machine-readable form.** That is missing schema semantics, not missing documentation. Were the mapping to live in the documentation repository, it would become a second source of truth that TiGL, TiXI, and other tools cannot see.

Symptoms in the current state: 113 of 340 reference elements without any documentation, 18 tautological descriptions, 9 names outside the convention.

### 10.3 Recommendation for a separate schema initiative

To be pursued as an independent CPACS development item with its own issue, **separate from the documentation project**. Preferred mechanism: a declarative annotation inside `appinfo`, invisible to validators and without effect on validation behaviour.

```xml
<xsd:element name="wingUID" type="stringUIDBaseType">
  <xsd:annotation>
    <xsd:appinfo>
      <cpacs:reference target="wingType"/>
    </xsd:appinfo>
    <xsd:documentation>UID of the referenced wing</xsd:documentation>
  </xsd:annotation>
</xsd:element>
```

Design notes:

- The target is given as a **type name**, not an element name. Types are the stable identity; collision risk arises precisely because element names recur with different meanings.
- Multiple targets must be permitted (`parentUID`, `entityUID`).
- "Any uID carrier" needs an explicit marker, so that *deliberately open* can be told apart from *not yet declared*.
- A new CPACS-owned namespace does not collide with E7: this is new information, not a rename of existing documentation blocks.

**Rejected: `xsd:keyref`.** There is a precedent in `versionKey`/`versionKeyRef` on the root element. Three points argue against it: the selector XPath addresses element names rather than types and would therefore be exactly as imprecise as the name heuristic; existing data sets with dangling references would become invalid overnight, a breaking change for the ecosystem; and roughly 226 keys plus 193 keyrefs scale poorly over CPACS-sized instance documents.

**Rejected: a registry file alongside the schema.** Defensible as an interim step, drift-prone as an end state.

**Bootstrapping.** The rejected heuristic retains one use, as a **one-time proposal generator**: a script produces 114 candidates, a human reviews them, and the result is committed as explicit declarations. The distinction matters — what ends up in the schema has been reviewed, and the heuristic appears nowhere in the output.

### 10.4 What the documentation system does today

Derive nothing, but report everything exact: N10 carries "reference element without documentation" as a diagnostic category, surfacing a concrete, actionable list for schema maintenance. Once explicit declarations exist in the schema, the viewer consumes them, and coverage grows visibly.

---

## 11. Migration

A preparatory phase followed by four phases, each usable and reversible on its own.

**Phase 0 — verification of load-bearing assumptions.**
Three throwaway experiments, run before anything is built on top of them: not-found routing on the actual deployment target (R2, N18) — **done for GitHub Pages, R2 confirmed**, findings folded into §2.1, §3.4, §3.5 and §8.2, raw data in `DLR-SL/spike-routing`, GitLab Pages deliberately left unmeasured; fidelity of the ddue renderer against the live Sandcastle output for a sample of twenty types spanning the vocabulary, including `math`, `definitionTable`, `table`, and `mediaLink`; and the `serve` edit-and-view loop (R4). If routing fails, E1 changes; if fidelity fails, acceptance criterion 1 changes.

**Phase 1 — extractor and model validation. Done.**
The extractor (`DLR-SL/cpacs-doc`) reads the schema, builds the type catalogue and the instance tree, resolves figure references against a media catalogue, and writes `cpacs-doc-model.json` plus the build report. The model carries `ddue` markup as plain text; rendering belongs to phase 2. Element declarations are stored once and referenced from the tree, which is what keeps the model at 13 MB rather than 75 MB. The figures in §1.1 were re-measured against the extractor and corrected. Two changes outside the extractor belong to this phase: the figure catalogue moved out of the SHFB project file into `documentation/media.json` (`tools/convert_media_catalogue.py`), and three `sd:schemaDoc` bodies using `ddue:content` instead of `ddue:remarks` are reported rather than reinterpreted.

Original scope for reference:
Implement the extractor, generate the model for v3.5.1, verify coverage against the figures in §1.1. Deliverable: `cpacs-doc-model.json` plus the build report — which is a usable result in its own right, since it turns undocumented types, undocumented reference elements, unexplained `sequence` compositors, and tautological descriptions into an actionable maintenance list that does not exist today. The repository README marks the work as experimental (E8). The Sandcastle build stays in production unchanged.

**Phase 2 — viewer prototype. In progress.**
The ddue renderer and the generator are done: the renderer covers all 25 vocabulary elements in Python, and the generator writes one static page per type plus the assets they need. The result is deployed as a preview from CI. Rendering happens once, in the generator, and the resulting fragments travel in the model — a second renderer in JavaScript would be a second thing to keep in step. Generated output carries no version and no deployment prefix: pages link relatively, and the router derives its prefix from the requested path at run time, so the output directory stays movable.

The tree canvas, the detail panel and client-side search are done as well. The tree is flat — indentation there means containment in an instance, and a compositor contains nothing — so nodes bound to a `choice` are marked rather than nested; the combinations are spelled out in the child table, where indentation describes a type. Search is built from the loaded model rather than from a separate index (§5), because a second artefact would carry the same data twice and have to be kept in step.

Remaining: `serve` mode, and the comparison against the existing documentation on a sample of types — the latter is acceptance criterion 1 and still entirely unverified.

Original scope for reference:
Tree canvas, detail panel, ddue renderer, search, `serve` mode. Deployed in parallel under a preview path. Compared against the existing documentation on a sample of types.

**Phase 3 — feature parity and cutover.**
Structural semantics (§6), diagram export, version switcher, diff stage α, GUID redirect map. The main path is switched over. The Sandcastle build continues through a transition period. The XSDDiagram link is downgraded only after `serve` mode is usable in production (§12, E5).

**Phase 4 — decommissioning.**
Remove `Cpacs_doc_project.shfbproj`, `Toolspecific_doc_project.shfbproj`, `Cpacs_doc_dsgvo.py`, `Help.content`, `development/3rdparty.zip`, `createDocumentation.bat`, `createToolspecificDocumentation.bat`, and the Windows build job. Update `development/buildDocumentation.md`.

### 11.1 Acceptance criteria for cutover

1. Every type documented in the Sandcastle output is present in the new system with substantively identical text (automated text comparison, tolerance only for whitespace and markup).
2. All 116 figures resolve and display.
3. Every legacy GUID URL redirects to a valid new path or to an explanatory page.
4. The full instance tree is navigable to every leaf; sample of 20 deeply nested paths.
5. Output size within the limits of §8.2.
6. `serve` mode processes an uncommitted working copy of the schema and refreshes after save without noticeable delay.

---

## 12. Decision record

| # | Question | Decision |
|---|---|---|
| **E1** | Rendering strategy and viewer technology | Pre-render only the 1,101 type pages; resolve tree paths client-side via `404.html`. See §3.4. The technology question thereby reduces to templating plus a client router and stays within the extractor's Python stack. |
| **E2** | Derivation rule for uID target types | **No derivation in v1.** The description text on the referencing element carries the orientation; N10 reports where it is missing. An explicit declaration mechanism remains a separate schema initiative. See §10. |
| **E3** | Scope of the diff view | **Stage α in v1**, β in v2, γ rejected. No automatic rename detection. See F18. |
| **E4** | Relationship to `cpacs-schema-tool` | **No dependency.** Standalone extractor; the tool serves as a reference for parser settings and diagnostic shape. See §3.1, N16, N17. |
| **E5** | Relationship to XSDDiagram | **Close the gap first, then downgrade.** `serve` mode (R4/R6) covers the remaining use case: any uncommitted XSD without a build step. XSDDiagram then moves from its prominent position to a "further tools" page, with an honest note that the detailed documentation is not visible there. **Do not remove it** — it works on arbitrary XSD files and is used by third parties independently of CPACS. **Do not fork it** — adopting a .NET 2.0 WinForms project frozen in 2019 would incur exactly the maintenance burden this initiative exists to shed, and the licensing situation in the repository is mixed (GPL/LGPL/MS-PL). |
| **E6** | Presentation of `xsd:all` | **Semantics-carrying presentation** plus compositor symbol, conspicuous rather than discreet. Extended by the classification of enforced ordering and by the cardinality requirements S3 and S4. See §6. |
| **E7** | Timing of a CPACS-owned documentation namespace | **Not in v1.** Vocabulary unchanged, but frozen normatively. See §5.3. |
| **E8** | Repository location and status | **GitHub**, with the README marking the work as experimental. The experimental label rather than a hidden location is what keeps expectations honest: the work is visible, but nobody mistakes it for a committed deliverable. Independence from the hosting platform is preserved as a requirement (N18), so the choice stays reversible. |

---

## 13. Remaining open points

Not yet ripe for decision, but blocking nothing:

| # | Point | Note |
|---|---|---|
| O1 | Machine-readable type renames in past releases | If the release process holds such a mapping, the diff view can read it. Otherwise two separate entries. |
| O2 | Concrete templating and client libraries | Reduced to a small requirement by E1. Criterion N14 applies. |
| O3 | Format and location of the "CPACS Documentation Vocabulary" document | Follows from E7. |
| O4 | Trigger and timing for diff stage β | Tied to the stabilisation of `meta.modelVersion`. |

---

## 14. Summary of core decisions

1. **A persisted intermediate model** between extraction and presentation — the decision on which all others depend.
2. **A combined fallback chain**, element documentation plus type documentation rather than either-or. This resolves the central shortcoming of both legacy tools.
3. **Path-based URLs** instead of GUIDs, with a redirect map for existing links.
4. **Pre-render type pages only**, resolve tree paths client-side — the only strategy that reconciles 53,692 citable paths with a shippable output size.
5. **Make structural semantics visible** — compositor, cardinality, effective obligation, and the cause of enforced ordering. This addresses a real user pain point and is fully derivable.
6. **Leave the vocabulary unchanged**, but freeze it normatively and decouple it from the dead originating projects.
7. **Resolve figures by convention** rather than by registration in a project file.
8. **Guess nothing.** No reference graph from a name heuristic, no rename detection. What is not exactly derivable is reported rather than presumed.
9. **Two operating modes** — `serve` for schema development, `build` for deployment. This replaces the use case XSDDiagram serves today.
10. **No dependency on `cpacs-schema-tool`**, whose future is open. Imitation by reference rather than coupling.
11. **Linux CI without binary blobs.** This removes the heaviest maintenance burden of the legacy chain.
