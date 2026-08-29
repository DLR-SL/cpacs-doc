# Comparison against the Sandcastle output

Date: 2026-08-28 · Acceptance criterion 1 · findings, with what has been closed marked as such

## What was compared

`build_sandcastle/doc` (5,055 pages, 3,360 distinct titles: 1,101 complex types,
8 simple types, 3,631 elements, 311 attributes) against a build of this tool
from `build_sandcastle/schema/cpacs_schema.xsd`. That file is byte-identical to
`D:/Entwicklung/CPACS/develop/schema/cpacs_schema.xsd` (SHA-256 `113ce4a9…`), so
both outputs describe exactly the same schema.

Two methods. Every facet in the schema was matched against the model **by source
line**, which is independent of naming conventions and catches what a name-based
lookup misses — a first attempt using carrier names reported 187 false gaps.
Then a sample of hard types was read page against page: `doubleConstraintBaseType`
(simpleContent, inline attribute enumeration), `ataChapterListType` (15
documented values), `toolType` (wildcard), `axleType` (inline element type),
`systemTypeType` (union), `cpacs` (identity constraints).

## Findings

### 1. Four fifths of the enumeration values are extracted but unreachable

The model holds all 265 values. Only 48 of them can be reached in the output —
the ones on named types (32 simpleType, 16 complexType). The other **217 sit in
anonymous types that nothing links to**:

| carrier | anonymous types | values | what the page says instead |
| --- | --- | --- | --- |
| element with an inline type | 50 | 187 | nothing: the declaration carries `type: null`, so the detail panel prints no type line at all, and the Type cell in the child table is empty |
| attribute with an inline type | 7 | 30 | the base type, `xsd:string`, in place of the inline one |

Sandcastle puts them on the element's or the attribute's own page, as a
*Content Type* table with columns Item / Facet / Value / Description. For
`sideOfFirstWheel`: `string`, then `Enumeration inboard`, `outboard`, `centre`.
Our page for the same element shows the description and stops. The description
happens to name two of the three values in prose; `centre` appears nowhere.

This is a linking defect, not an extraction one — the values are already in the
model, addressable as `axleType/sideOfFirstWheel`. Covers the ToDo entries
*"enumeration items not listed"* and *"inline type-specifications not displayed
correctly"*.

> **Closed, 2026-08-28.** A declaration that names no type now names the one it
> declares, in all three places that refer to one: child rows, attribute rows
> and tree nodes (`content.inline_reference`). Measured against the same schema
> afterwards: declarations without a type 88 → **0**, enumeration values
> reachable from a declaration or an attribute row 48 → **265**, statistics
> unchanged. The tables label such a type with its base rather than its
> synthetic name — `xsd:string`, not `axleType/sideOfFirstWheel` — and keep the
> link, because that page is where the values are.
>
> The link alone turned out not to be signal enough: `xsd:string` in a row reads
> exactly like the plain string beside it, and nothing tells a reader who has
> not met the convention that there is anything to open. The tables therefore
> carry a **Constraints** column naming what sits behind the link — `3 values`,
> `pattern`, `minInclusive, maxInclusive` — linked to the same page, so the
> words that name what the reader is after are themselves the way there. XSD
> calls an enumeration a constraining facet, which is why one column holds both.
> It appears on 262 of the 7,685 rows across all type pages.

### 2. No facet other than `enumeration` is extracted at all

30 constraints are lost, every one of them:

| facet | count | carriers |
| --- | --- | --- |
| `pattern` | 8 | `doubleArrayBaseType`, `doubleVectorBaseType`, `posIntVectorBaseType` (the `;`-separated vector grammars), `naca4DigitCode`, `naca5DigitCode`, `prioritySetting`, `wayPointType`, `variableConditions` |
| `minInclusive` | 9 | `controlPointNumber` (4), `phi`, `share`, `fillFactor`, `posOnBogie`, … |
| `maxInclusive` | 6 | `posOnBogie` (1), `phi` (360), `relativePosition`, … |
| `minExclusive` | 5 | `posExcl0DoubleBaseType`, `posExcl0IntBaseType`, `maximumError`, … |
| `maxExclusive` | 2 | `cornerRadius` (0.5), `lowerHeightFraction` (1) |

`content.py::_enumeration` walks the restrictions but reads only
`xsd:enumeration` from them. Sandcastle lists all of them in the same facet
table. A reader of `phi` cannot learn from us that it is bounded to 0…360, nor
that `naca4DigitCode` is exactly four digits. Covers the ToDo *"restrictions not
accounted for?"*.

> **Closed, 2026-08-28.** `content._facets` reads every constraining facet XSD
> defines along the same paths the enumeration already used, and the model
> carries them as `facets` (version 1.2, `statistics.valueConstraints`).
> Measured against the same schema afterwards: **30 of 30** — 8 `pattern`,
> 9 `minInclusive`, 6 `maxInclusive`, 5 `minExclusive`, 2 `maxExclusive`.
> Pages and panel show them as *Value constraints*, the schema word carrying
> its plain reading on hover and focus as a compositor does, and the row that
> leads there names the facet rather than counting it — `pattern`, not
> "1 constraint", because 121 of the 262 marked rows carry exactly one. Together
> with finding 1 this reaches the elements that declare their own type: the
> panel for `naca4DigitCode` now reads `Type: xsd:string` and `pattern
> [0-9]{4}`.

### 3. The value type of a `simpleContent` type is never stated

22 named types extend a simple type and therefore hold a value themselves.
Sandcastle names it outright — `Content Type: double` on
`doubleConstraintBaseType`. We give one hop of the chain (`extension
doubleBaseType`) and leave the reader to walk `doubleConstraintBaseType →
doubleBaseType → xsd:double` across three pages to find out what to write into
the element.

> **Closed, 2026-08-28.** `model.content_types` resolves the chain once for
> everyone and the model carries `contentType`. **104** types hold a value —
> the 22 with simple content, the simple types, and the inline types declared
> at an element or an attribute — and for **64** of them it says something the
> base does not. Shown as `· value xsd:double` on the kind line and on the
> node's own type line, and left out where the base has already said it, so
> `doubleBaseType` still reads `extension xsd:double` and nothing more.

### 4. `xsd:any` is dropped from the child table, documentation and all

One occurrence, in `toolType`, where it is the point of the type. Sandcastle
lists it as a child row named `Any` and carries its description, *"Wildcard for
the root element of a toolspecific namespace"*. Our child table shows `name` and
`version` and gives no sign that anything else may appear.

> **Closed, 2026-08-28.** `content._read_wildcard` reads it with its namespace,
> its `processContents` and its documentation, and the child table gives it a
> row: `any · ##any · strict · 1`, the schema word carrying its reading as a
> compositor does. Namespace and processContents carry the values XSD gives
> them where the schema is silent, as the occurrence fields already did.
>
> It gets no tree node: a wildcard has no name, so it has no instance path, and
> the tree is instance paths (0008). The node's own table is where a reader
> meets it.
>
> The deeper defect was the silence. `_read_group` passed over anything that
> was neither a compositor nor an element without a word, which is how the
> wildcard came to be missing in the first place — so an unknown construct is
> now reported as `CHILD_CONSTRUCT_UNSUPPORTED`. Against this schema it fires
> **0** times: `xsd:any` was the only thing being dropped.

### 5. Identity constraints are not shown

`xsd:key` and `xsd:keyref` on the `cpacs` element. Sandcastle has a *Constraints*
table — Type / Description / Selector / Fields — showing the key on
`./header/versionInfos/*` `@version` and the reference from `./header` `version`.
We show nothing, so the one integrity rule the schema states is invisible.

> **Closed, 2026-08-28.** `tree._identity_constraints` reads `key`, `keyref`
> and `unique` from the declaration in document order — a keyref may stand
> before the key it names, and here it does — and the node carries them into
> the model as `identityConstraints`. The panel shows them at the foot of the
> node, below what the type says: the rule is about this element, but one node
> of 53,692 carries one, and above the prose it would cost every reader of the
> root node a screen to get past it.
>
> | Constraint | Name | Refers to | Selector | Fields |
> | --- | --- | --- | --- | --- |
> | `keyref` | versionKeyRef | versionKey | `./header` | `version` |
> | `key` | versionKey | | `./header/versionInfos/*` | `@version` |
>
> The schema word carries its reading on hover and focus, as a compositor does.
> The static pages do not show it and should not: the rule hangs off the
> element, the type is not where it was written, and this architecture has no
> element pages.

### 6. "Used by" is missing (known: F10)

Sandcastle lists *Usages* on every type page (34 elements for
`doubleConstraintBaseType`) and *Parents* on every element and attribute page.
We carry `firstPaths`, which is one path per type and exists to give the page a
way back into the tree. Confirms the ToDo *"parents-list in type documentation
could actually be useful"* as a real regression against the predecessor, not
only a wish.

> **Closed, 2026-08-28.** A *Used by* section on the type page and in the type
> view, folded away in a `details` — it answers a question that is asked now and
> then, and `details` opens with the keyboard and works on a page with no
> script. It holds two lists, and the headings name the **level** rather than
> the contents, because both lists are elements and that is what tells them
> apart:
>
> - **In a dataset · N paths** — where the type stands in a document, linked
>   into the tree. First, because it is the concrete answer and the one neither
>   predecessor could give.
> - **In the schema · N declarations** — a `Type`/`Name` table of the
>   declarations that name it.
>
> **Derived, not stored**, for the reason 0009 gives about the search index —
> both facts are in the model already, and a second copy would have to be kept
> in step. Measured before deciding: storing the paths would be **+8.28 MB raw**
> beside a 4.20 MB model (gzip +0.27 against 0.34). The generator derives them
> at build time, the viewer on the first type view, where the whole pass —
> 1,206 types and 54,552 tree nodes — takes **10 ms** once. Writing the capped
> path lists into all 1,206 pages costs 0.74 MB, and only 63 types (5 %) reach
> the cap at all.
>
> Both lists are capped at 25 with *and N more*, as the search shows sixty of a
> thousand. Both walks push children in reverse so the paths come out in
> document order: with a capped list, *and N more* has to mean the ones after
> these.

### 7. "Inherited from" is right and reads wrong

The ToDo asks why the column says `complexBaseType` for an attribute of type
`xsd:string`. The data is correct: `externalDataDirectory` **is** declared in
`complexBaseType` and its type **is** `xsd:string`; the two columns answer
different questions. Sandcastle has no such column at all, so there is nothing to
copy — this is a labelling decision, not a defect.

> **Closed, 2026-08-29.** The column is gone from both tables, the static page
> and the detail panel. It answered a question no reader had asked — where the
> attribute was declared — right next to the one they had, and read as a
> contradiction of the Type column. 1,051 of 1,206 types derive from
> `complexBaseType`, so the column said the same word on nearly every page.
> `inherited` and `declaredIn` stay in the model, and inherited attributes are
> still listed first (ADR 0005), so nothing is lost that a later marker could
> not use.
>
> Open against this: requirement D2 asks that inherited content be *visually set
> apart* and hideable. With the column gone, nothing in the output says which
> attributes are inherited. Either D2 is amended, or the mark returns without a
> column of its own — a quiet word on the name cell, the declaring type on
> hover.

### 8. The union is empty on both sides

`systemTypeType` unions `individualSystemCategoriesType` and
`ataChapterListType`. Our page shows `simpleType` and nothing else; the
Sandcastle page shows nothing either. A gap against the schema, not a regression.

> **Closed, 2026-08-29.** `xsd:union` is read (model version 1.3, key `union`)
> and the members are a table of their own — *Allowed types*, with the schema
> word `union` beside the heading carrying the plain reading on hover. The
> Constraints column is the child table's, so the page says what is behind each
> member before the click: `individualSystemCategoriesType` 1 value,
> `ataChapterListType` 15. Those 16 values were reachable from nowhere near
> this type before.
>
> The row that points at the union says `one of 2 types` in the same column —
> a union carries neither values nor facets, so without it the one row in the
> schema that references one (`systemType` in `systemArchitectureType`) looked
> like a plain type with nothing behind it. This is finding 1's defect in
> another guise.
>
> `xsd:list` and a union that declares a member type inline are reported as
> `VALUE_CONSTRUCT_UNSUPPORTED` rather than passed over. The schema uses
> neither — one union, no list, no inline member — so the count of warnings
> against CPACS 3.5.1 is unchanged at 64.

### 9. A declared default is invisible on both sides

Twelve element declarations carry `default` — `controlPointNumber` 12,
`maximumError` 1e-5, `phi` 0.0, three `reinforcementNumber*` 0, `continuity`
and `interpolation` 0 at four places each. Sandcastle's page for
`controlPointNumber` shows its type, its `Min Inclusive 4` and its parents, and
not the default. Neither did we. A reader who cannot open the schema had no way
to learn what leaving the element out means.

> **Closed, 2026-08-28.** `default` and `fixed` are read from element
> declarations, carried on child rows and on tree nodes, and shown in a
> *Default* column beside the one the attributes table already had, and on the
> node itself: `occurs 1 · default 1e-5`. The two are kept apart rather than
> folded into one field — a default is what an instance means by leaving the
> element out, a fixed value the only one it may write — and the column says
> which. All 12 are carried; the schema uses no `fixed`.

## Where the new output is ahead

Attribute tables carry `use` and `default` and name the declaring type;
Sandcastle has Name / Type / Required / Description and no default. Enumeration
descriptions sit in the same table as the values (43 of 265 are documented)
rather than being repeated below it. Occurrence is shown per path rather than per
declaration, choice membership is marked at the node, and the search and the
handbook split have no counterpart at all.

## Differences that are not defects

Sandcastle documents 3,631 **elements** as pages of their own, each with its
parents; this tool resolves 53,692 instance paths in the browser and writes pages
only for the 1,206 types. That is the architecture, decided in the specification,
and the reason the element pages have no equivalent here.

Two ToDo entries turn out to have no precedent to copy: Sandcastle writes
occurrence as `[0, 1]` after the name, which is no more prose than our `0…1`; and
it does not link `xsd:string`, `xsd:double` to their official descriptions
either.

## Not compared

Rendered `ddue` prose was not compared page by page — only its presence. Media,
tables and cross-references inside the documentation bodies are unexamined, as
are the 3,631 element pages beyond the two read for findings 1 and 5.
