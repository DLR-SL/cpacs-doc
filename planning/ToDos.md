# Notes on ToDos, Bugs and Findings

- Undo function of the browser only works affects the tree
- xsd:types link to official description?
- should it be a bit more visible what is element and what is type documentation?
- type pages scroll sideways, and it is the page that scrolls, not the table:
  the heading, the prose and the breadcrumb slide with it. The text column is
  968 px wide (`max-width: 58rem`); measured at a 1280 px viewport on
  2026-08-29, the child table is 1,143 px on `wingType`, 1,119 px on
  `fuselageType`, 1,073 px on `genericMassType` — 105 to 175 px over. All
  1,079 type pages with a child table are affected. Code blocks already solve
  this with `overflow-x: auto` on their own container (styles.css:336); the
  tables have no such container. Contributing: `td code` is set `nowrap`, and
  the attributes table alone is 753 px at a 700 px viewport (measured
  2026-08-28 on `doubleBaseType`, which has no other content).

- two of the six columns are empty on almost every page, and the eye crosses
  them on every row. Measured 2026-08-29: of 1,079 child tables, *Constraints*
  is empty in every row on 993 (92 %) and *Default* on 1,073 (99 %), both on
  992 (92 %); of 1,161 attribute tables, 1,109 (96 %) and 1,147 (99 %).
  Dropping a column where every row in that table is empty gives back 45 to
  105 px — `genericMassType` lands exactly on the 968 px text column and stops
  scrolling altogether. Against it: the column set would differ between pages.
  For it: whole tables already do.

- the detail panel's head carries two horizontal rules within 120 px — one
  under the occurrence line, one under the type line — cutting a single head
  into three blocks.

- 41 of the 672 types that carry both begin their `remarks` with the `summary`
  verbatim (6 %, measured 2026-08-29), so the panel shows the same paragraph
  twice. The schema's own content, not a rendering fault; a finding for the
  schema rather than something to drop silently.

- Child elements table
    - first "all" icon: a bit of space on the left
    - is type benefitial here? (open discussion)
    - if no element description, but type summary, then use this? (open discussion; what can go wrong? Is the the wanted behavior?)

- Attributes table:
    - description: use type documentation, if element-description is missing (see above)

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