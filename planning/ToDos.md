# Notes on ToDos, Bugs and Findings

- `occurs 1` --> more intuitive description
- Undo function of the browser only works affects the tree
- xsd:types link to official description?
- should it be a bit more visible what is element and what is type documentation?
- type pages scroll sideways in a narrow window: the attributes table is 753 px
  wide at a 700 px viewport, because `td code` is set `nowrap` and the table has
  six columns (measured 2026-08-28 on doubleBaseType, which has no other content)

- Child elements table
    - first "all" icon: a bit of space on the left
    - is type benefitial here? (open discussion)
    - if no element description, but type summary, then use this? (open discussion; what can go wrong? Is the the wanted behavior?)

- Attributes table:
    - Why "Inherited from" is "complexBaseType", if attribute is of simple XSD type (e.g., `xsd:string`)
    - description: use type documentation, if element-description is missing (see above)



### Closed

Written up with numbers in `planning/sandcastle-comparison.md`, findings 1, 2
and 6.

- enumeration items not listed
- inline type-specifications not displayed correctly
- restrictions not accounted for?
- parents-list in type documentation could actually be useful


### Crazy ideas for future
- expert mode? (e.g., show types, else not)
- Portable app via electron (or similar framework)?
- Canvas tree
- AI chatbot