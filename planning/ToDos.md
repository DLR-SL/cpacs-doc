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



### Closed

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