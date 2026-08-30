# Notes on ToDos, Bugs and Findings

- Undo function of the browser only works affects the tree
- the viewer's detail pane has the same defect one level down: the child table
  needs 1,110 px in a 718 px pane, so the pane scrolls sideways by 376 px and
  the heading of the type goes with it. Measured 2026-08-30 at 1280 × 900, the
  same on `wingType`, `fuselageType` and `genericMassType`. The pane's tables
  are written in `viewer.js`; the container and its rule are already there.

- the tables `ddue` writes into prose need no container today: 6 stand on the
  documentation pages, none wider than its column, and no type page is past the
  window either (measured 2026-08-30 over all 1,206). Worth measuring again
  when the schema grows a wide one.

- two of the six columns are empty on almost every page, and the eye crosses
  them on every row. Measured 2026-08-29: of 1,079 child tables, *Constraints*
  is empty in every row on 993 (92 %) and *Default* on 1,073 (99 %), both on
  992 (92 %); of 1,161 attribute tables, 1,109 (96 %) and 1,147 (99 %).
  Dropping a column where every row in that table is empty gives back 45 to
  105 px — `genericMassType` lands exactly on the text column and stops
  scrolling altogether; since 2026-08-30 that is the table's own scrolling and
  no longer the page's. Against it: the column set would differ between pages.
  For it: whole tables already do.

- 41 of the 672 types that carry both begin their `remarks` with the `summary`
  verbatim (6 %, measured 2026-08-29), so the panel shows the same paragraph
  twice. The schema's own content, not a rendering fault; a finding for the
  schema rather than something to drop silently.

- Child elements table
    - first "all" icon: a bit of space on the left
    - is type benefitial here? (open discussion)

- the description of an element or an attribute is its own, and stays empty
  where the schema leaves it empty (decided 2026-08-30, for now). Sandcastle
  fills it from the type — `useTypeDocumentation forUndocumentedElements` in
  `Cpacs_doc_project.shfbproj:25`, on since the current build — and its pages
  show what that is worth: `centerFuselageKeelbeamType/sheetElementUID` reads
  `stringUIDBaseType`, `massDescription` reads "Mass description" and then the
  whole remarks of `genericMassType`, examples included.

  Measured 2026-08-30 on the real schema. 1,658 of 3,663 element declarations
  carry no description of their own; the fallback would fire on 1,611 of them
  and fill 837 (52 %) with the type's name spelled out and 297 more with a
  sentence that only repeats the element's name. 477 rows — 13 % of all
  declarations — would learn something. On 138 type pages the same borrowed
  sentence would stand in 482 rows twice or more. For attributes it fires 14
  times in 4,022 declarations, since attribute types are built-in ones that
  carry no documentation, so `forUndocumentedAttributes` buys nothing here.

  The way it would be worth having is the one A1 already prescribes — element
  text and type text combined and the provenance marked, never a substitute —
  with a guard against borrowing a sentence that only repeats the type's or the
  element's name. Not built: the answer is better element documentation in the
  schema, which is where the gap is.

- **A schema finding, for the documentation work:** 393 of the 1,089 types with
  a summary (36 %) have their own name as that summary — `stringUIDBaseType`
  (`cpacs_schema.xsd:2081`), `doubleBaseType`, `genericCostType` and so on —
  and all 393 carry real remarks underneath. The report says nothing about it
  today and `documentedTypes: 1121` counts them as documented, so the coverage
  figure is that much too kind. A finding of its own would put them on a list
  worth working off.

- Decide requirement D2: with the "Inherited from" column gone, nothing marks
  inherited attributes. Amend D2, or bring the mark back without a column.



- search: decide whether the per-kind quota stays. If it does, it deserves an
  ADR next to 0009, and F13 in the specification should say that ranking
  decides the order while the quota decides who is cut off at sixty. Not
  written down as a decision yet because it is on trial. (The chips and the
  prefixes are settled: 0013 keeps both and gives the forms a home.)

- search: the corpus is 91 % repetition — 53,692 element entries are 2,224
  distinct names (`x` alone is 5,280 of them), 4,022 attribute entries are 23
  distinct names. One entry per name, with its places listed the way "Used by"
  lists them, would make the ranking meaningful rather than propped up by a
  quota. It costs a click on the way into the tree, which is the part of the
  quick search that works today, so it is a separate decision.

  **On trial since 2026-08-30, not decided.** A name standing in more than one
  place is one row saying how many, and opens its places under itself. A path
  query is never grouped — a reader who names a place is asking for places.

  A threshold was tried first and dropped. Measured in a browser on the real
  schema, 1174 × 807, nine queries. Two figures per query: how many of the
  sixty rows on screen have their path cut at the front, and how long the whole
  list is.

  | GROUP_MIN | `mass` | `segment` | `wing` | `uid` | `translation` |
  | --- | --- | --- | --- | --- | --- |
  | none | 45 cut / 8,515 | 41 / 21,496 | 38 / 8,218 | 39 / 15,187 | 60 / 6,886 |
  | 2 | 3 / 286 | 12 / 506 | 7 / 611 | 6 / 653 | 1 / 13 |
  | 3 | 28 / 358 | 18 / 543 | 27 / 722 | 19 / 724 | 1 / 13 |
  | 5 | 40 / 398 | 36 / 743 | 38 / 917 | 30 / 889 | 15 / 23 |
  | 10 | 40 / 404 | 39 / 1,117 | 37 / 1,523 | 30 / 984 | 33 / 39 |

  Two things the numbers say. The threshold does not trade one good against
  another: at 5 and above the truncation is back to where it was without
  grouping at all, because a name standing in two, three or four places is the
  common case and each of those keeps a path row. And the list gets *longer* as
  the threshold rises — 286 rows at 2 against 404 at 10 for `mass` — since
  fewer names are folded. So there is no threshold: a name folds from its
  second place.

- search: **a query that is not a path no longer reads paths** (2026-08-30,
  with the grouping above). Every descendant of a `wingCutOut` carries the name
  in its own path, so `wingCutOut` was answered with `eta`, `xsi` and the rest
  of what stands under one — and grouping made it worse, because folding the
  name matches into few rows left room for hundreds of them. Paths are read
  where the query is a path, which is the form with a slash in it, and the `?`
  strip already teaches that.

  **F12 and F13 are amended** for it (2026-08-30), both in the specification.
  What it costs, measured the same way, is
  the reading of a query as a place-in-the-schema without saying so: `mass`
  now answers 69 rows where it answered 8,515, `segment` 155 where it answered
  21,496, and the count on the chips is a number a reader can act on.

  | query | rows before | cut before | rows now | cut now |
  | --- | --- | --- | --- | --- |
  | `mass` | 8,515 | 45 of 60 | 69 | 9 of 60 |
  | `segment` | 21,496 | 41 | 155 | 14 |
  | `wing` | 8,218 | 38 | 168 | 9 |
  | `uid` | 15,187 | 39 | 530 | 6 |
  | `translation` | 6,886 | 60 | 10 | 1 |
  | `wingCutOut` | — | — | 6 | 0 |

  Open with it, and not answered by it: the chips now count rows rather than
  places, so `mass` reads `Elements 327` where it read `Elements 8,484`. Each
  group states its own count, so nothing is hidden, but the corpus size is no
  longer on screen anywhere. `Enter` in the field opens the top hit; where that
  is a group, it opens the group rather than going to the tree. The places
  under a name are cut at 25, as "Used by" cuts at 25.

  The two left edges — a folded name starts 1.3 rem in behind its `+`, a name
  with one place at the margin — are wanted: the indent is the sign of which
  rows open and which jump.

- search: **a place inside a group is written out, not cut** (2026-08-30).
  0013 argued that truncating a path at the front is safe because the tail
  tells two occurrences apart. Between different names it does. Within one name
  it does not, and that is the case grouping creates: the nine places of
  `wingCutOut` read as three tails repeated three times, because what separates
  them is `aircraft` against `rotorcraft` and `wings/wing` against
  `rotorBlades/rotorBlade`, all of it in the part that is cut.

  Measured on the real schema over the 1,279 names that fold, counting the
  names that have two places a row cannot tell apart. A parent path is 140
  characters at the median and about 45 fit on a line:

  | the row shows | names with two places alike |
  | --- | --- |
  | the tail, cut at the front (as 0013 has it) | 895 (70 %) |
  | the front, cut at the end | 669 (52 %) |
  | the front and the tail, cut in the middle | 635 (49 %) |
  | the same, with the segments the group shares dropped | 399 (31 %) |
  | the whole path, wrapped | **31 (2 %)** |

  No one-line form gets under a third, because the paths are three times the
  room a line has and differ at both ends. So the place rows wrap and carry the
  path whole, broken at the slashes — a `wbr` after each, since the wrapping
  left to itself split `componentSegment` down the middle. Three lines at the
  median, four at the ninth decile, six at the worst. The 31 that stay alike
  are the schema's own: two places with one path, which the report already
  carries as `TREE_PATH_AMBIGUOUS` (860 of them).

  What this does not do is make 613 places findable by reading them. It makes
  25 of them tell each other apart. Whether a group wants something other than
  a list — its places by their first differing segment, say — is the question
  after this one.


### Closed

**What may be written here, in words** (2026-08-30). The value line names the
datatype in plain words with the schema's own term behind it — `Value: decimal
number (xsd:double)`, `reference to an identifier (xsd:IDREF)`, `text
(xsd:string)`. It reaches 37,843 of the 54,552 nodes: 28,203 of them `double`,
5,061 `string`, 4,230 `IDREF`, and those three are exactly the names that say
nothing to a reader who has not met them.

Nine words, for the datatypes a short phrase states exactly; the other 35 the
reference documents get none, because a word that promises more than the type
holds is worse than the name alone. The name stays in every case — it carries
the link, and it is what a validator, TiXI or an error message will say.

Where the type narrows the value, the line says so with the same vocabulary the
Constraints column uses: `· minInclusive, maxInclusive`, `· 5 values`, `· one
of 2 types`. Facets are named rather than counted, values counted rather than
named. It reaches 1,199 nodes, and the table that spells it out stands further
down the same panel.

Two things that came out of building it. A type declared on the spot had its
base named on the first line as `· type xsd:string`; it belongs on the value
line, which is where the question is answered — with the difference that this
name leads to that type's own page and its citable address (0003), while a
built-in content type leads out to the reference. Both are written `xsd:…`, so
the panel decides which link it is rather than the reader guessing from the
look. And the tables keep the notation in front (`[0..1] optional`): there it
is six characters wide on every row, so both parts line up in columns of their
own, which is worth more in a surface that is scanned.

**A built-in datatype leads to what it allows** (2026-08-30). `xsd:string`,
`xsd:ID`, `xsd:double` and the six others the schema uses have no page here —
they are not in the schema — so a reader who wanted to know what `xsd:IDREF`
permits had to leave the documentation to find out. They now link to Priscilla
Walmsley's XML Schema 1.0 reference at datypic,
`https://www.datypic.com/sc/xsd/t-xsd_<name>.html`, in a tab of their own so
the tree keeps its place.

data2type was where this pointed first and was dropped the same day: it is a
German site, and this documentation is written in English. The two English
candidates were the W3C recommendation — normative, permanent, and written as
specification prose — and datypic, which explains each type with values that
are valid and values that are not. The link exists for the reader who does not
know the type, so it goes to the one that answers that reader.

They are set in the soft ink rather than the link colour: a type name leads
further into what is written here, a built-in name is the last stop and leaves
the site, and `xsd:string` alone stands in 3,624 rows — too many for a mark on
each. Measured against the page: 5.9 to 1 in light, 6.8 in dark, against 6.5
and 7.9 for a link that stays. The underline is what says "link", so nothing
rests on the colour, and hovering or focusing brings it up to a link's own.

The 46 built-in names of XSD 1.0 are written out in `generator.py` and again in
`viewer.js`; every one of them was requested on 2026-08-30 and answered. The
name keeps its capitals in the address, as it does in the schema. A name that
is not among them stays text: an address derived for it would be a guess, and a
dead link is worse than a word — a test holds that too.

**The value has a line of its own** (2026-08-30). `Occurrence: [0..1] may appear
at most once · value xsd:string` answered two questions in one line, the second
riding on the end of the first. They are two lines in one block now, a line
apart, with the air under the block.

**Whose words these are** (2026-08-30, `decisions/0015`). The element's text and
the type's were set alike, with the `Type:` line as the only boundary. What
belongs to the place now stays unmarked; what the type lends is opened by one
line, `About the type <name>`, with a tick beside it — the prose itself keeps
the margin, because on many nodes it is the substance of the panel and a rail
down its side read as a quotation. Measured over all 54,552 nodes: 41,004 carry both kinds of text, 12,980 only
the type's — where a general sentence read as a statement about this place — 387
only their own, 181 neither.

The `Type:` line is gone; the type is named where its words begin, and on the
568 nodes whose type has nothing to lend the head names it instead. Both rules
the head carried within 120 px go with it — the second one only separated,
which the space already does — which was a ToDo of its own. Counted on the
panel of `translation`: 50 strokes, of which the tables draw 48 and the rail 1.

Three arrangements were drawn on real content and compared in a browser. The
line without the rail is lighter and leaves the end of the borrowed block
unmarked; the owner in the margin needs 52 rem and the detail pane is 718 px,
so it would have folded above the text and been the first with extra lines.

Held by `tests/test_viewer_provenance.py` on `fixtures/provenance.xsd`, a node
in each of the three cases.

**The table scrolls, not the page** (2026-08-30, `decisions/0014`). Every table
on a type page stands in a container of its own — `div.cd-scroll` with
`overflow-x: auto`, the way a code block has done all along — so the heading,
the prose and the breadcrumb stay where they are while a column on the right is
read.

Measured in a browser on the real schema at 1280 × 900, over all 1,206 type
pages: 1,079 carry a table wider than the 928 px column (the 58 rem measure
less its padding), and none of the 1,206 is now wider than the window. Before
it, `wingType` stood 46 px past the window at 1280 px and 478 px at 700 px.

What it costs, and where that went:

* `overflow-x: auto` makes the other axis a scroll container too, and a tip is
  laid out even while hidden — so the container carried a vertical scrollbar
  for a tip nobody had opened. Hence `overflow-y: clip`.
  `overflow-clip-margin` is the declaration that would leave the tips their
  room, and Chrome ignores it on a scroll container.
* The clip cuts a tip that opens past the last row, and that is where 20 of the
  2,319 tips in tables stand: cut by up to 23 px, one of them by 46. They open
  upwards instead (`.cd-scroll tr:last-child .cd-tip`), where the rows above
  leave 46 px at the least against the 41 a tip and its gap take. Measured
  again over all 1,206 pages: none cut.

Held in a browser by `tests/test_page_tables.py` — the page does not scroll,
the heading does not move while the table is scrolled to its end, and the tip
on the last row is drawn whole — on `fixtures/wide.xsd`, whose names alone are
wider than the column. Three of the four fail without the two rules; the
fourth states the premise, that the table is wider than the column it stands
in, and is there so the other three cannot pass by measuring nothing.

**Where the search lives** (2026-08-30, `decisions/0013`). It is a third
permanent tab with the field inside it, the chips on one line under the field,
and the query forms as a second line in the `?` strip. Drawn first in
`mockups/search-tab.html`, which also records what the arrangements that were
not taken cost, measured. What it deliberately does not settle is the width a
result row has for a path — 352 px, 0.9 % of the schema's paths whole — because
that waits on the grouping question still open above, which comes first.

Written up with numbers in `planning/sandcastle-comparison.md`, findings 1, 2,
6, 7 and 8.

**`occurs 1`** (2026-08-29). Two readers, both served, in this order: the
bounds, then the English for them.

* The node line: `Occurrence: [0..1] may appear at most once`. The bounds are
  always there and always exact; the sentence is a gloss and simply does not
  appear where there is no plain English to be had (a bound that forbids the
  element, say). A future combination therefore degrades to a correct statement
  rather than to an invented phrase. The modal is what makes it a rule —
  `occurs 1` read as a count of what stands in a dataset.

  **Turned round on 2026-08-30**: `Occurrence: may appear at most once [0..1]`.
  The head is read, not scanned, and the reader who has never met `[0..1]`
  should not have to step over it to reach the sentence; the one who wants the
  exact form finds it in the same line. What does not change is which of the
  two may go missing: with no plain English the line opens with the notation
  and states a fact. The Value line below it reads the same way, and one head
  with two grammars was the thing to avoid.
* The Occurrence column: both on one line — `[0..1] optional`,
  `[1..1] required`, `[1..∞] one or more`, `[0..∞] any number`, and
  `2 or more`, `up to 2`, `1 to 2`, `exactly 3` for the 20 declarations that
  are none of those. The cell is `nowrap`: left to itself it wrapped into two
  lines and cost up to 30 % of the table's height (`wingType` 623 → 474 px,
  `fuselageType` 790 → 557 px at a 1180 px viewport). The width is unaffected
  either way — the column takes its 18 px from the slack in the table, whose
  total is 1,073 px on `genericMassType` with the bounds and without them.
* The column heading carries the bridge to the schema — `minOccurs` and
  `maxOccurs` — on hover.
* The tree rows keep the compact form, now spelled `0..1` and `1..∞` so there
  is one notation and not two. A word per row would crowd out the names in a
  list of 54,552.

Read as UX afterwards (2026-08-29), three things it still owes:

1. **The hierarchy is inverted.** The bounds are set in `--ink-soft`, the word
   in full text colour — so the part that is always exact, and that the design
   says is the fast target, is the quieter of the two. The eye lands on
   `required`, not on `[1..1]`. Both should be set alike: the cell is one
   statement, not a word with a footnote. (The tree's compact form stays quiet
   for the opposite reason: there it is an aside to the name.)
2. **87 % of the rows say it twice.** 3,184 of 3,663 declarations are
   `[1..1] required` or `[0..1] optional`. The word teaches the notation on
   first contact and is wallpaper by the thirtieth row of a page — the argument
   `_holdings` already makes about a column of "1 constraint". Not a reason to
   drop it now; a reason to measure again once readers have settled in, and
   then to consider keeping the word only on the node line.
3. **The vocabulary answers two questions at once, and the notation covers for
   it.** `required`/`optional` say whether, `one or more`/`any number` say how
   often. So `[0..∞] any number` *is* optional and does not say so: a reader
   scanning for "optional" misses those 110 rows, one scanning for "required"
   misses the 349 that say `one or more`. The bracket repairs exactly that —
   `[0..∞]` opens with a zero, which is the answer. That is the case for
   carrying both, and the case against ever dropping the notation.

Also open: whether the `1` on 1,527 tree rows earns its place. Nothing else
marks the default case.

Watch: all bracket forms in this schema are six characters wide, which is why
the words line up in a column of their own. A future `[12..∞]` would push one
row's word a character right.

- enumeration items not listed
- inline type-specifications not displayed correctly
- restrictions not accounted for?
- parents-list in type documentation could actually be useful


### Crazy ideas for future
- expert mode? (e.g., show types, else not)
- Portable app via electron (or similar framework)?
- Canvas tree
- AI chatbot