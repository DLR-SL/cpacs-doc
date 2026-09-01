# 0016 — The cursor's mark is not the focus ring

Date: 2026-09-01

## Context

0010 settled that the cursor and the selection are different things and are
marked differently, and its consequences say both have to be visible at once.
What it did not say is that the cursor's mark must also differ from the mark
for *where the keyboard is* — and it did not, because one rule drew both:

```css
.cd-node.cd-cursor,
.cd-node:focus-visible { outline: 2px solid var(--link); outline-offset: -2px; }
```

Readers reported being lost after Enter. Measured in a browser, pressing Enter
on `wings` and then ArrowDown twice:

| | cursor row | activeElement | detail scrollTop |
| --- | --- | --- | --- |
| before Enter | `wings` | the row | 0 |
| after Enter | `wings` | `#cd-detail` | 0 |
| after ↓ ↓ | `wings` | `#cd-detail` | 8 |

Both marks were `solid 2px rgb(116, 179, 240)` at that moment, one in each
pane. So the screen said the keyboard was still on `wings` — in the same words
it uses everywhere else for exactly that — and the next arrow key scrolled the
panel instead of moving a cursor the reader believed he still held. The break
was not the jump; it was that nothing on screen distinguished having jumped.

## Decision

- The cursor row, while the keyboard is elsewhere, is `1px dashed
  var(--ink-soft)`. The focus ring stays `2px solid`. Both keep
  `outline-offset: -2px`, so they share an outer edge and the row does not
  shift as the focus comes and goes. The focus rule follows the cursor rule at
  equal specificity, so the focused cursor row takes the ring and no row is
  drawn twice.
- ArrowLeft steps out of the detail panel, the direction the tree already uses
  for stepping out of a node. Only on an event the panel itself received.
- The focus ring has a colour of its own, `--focus`, and no longer borrows
  `--link`.

## Rationale

**Not removing Enter's jump.** It is one line, and it makes Enter identical to
Space while costing the keyboard reader the only way to scroll the detail panel
— which carries `tabindex="-1"` and is not in the tab order. The jump is not
the fault; its invisibility was.

**Not a notice that fades in on the panel.** It fires on every Enter or needs a
seen-state of its own beside the one the hint already has; it appears where the
eye is not; and a fade has to be caught. It also answers "how do I get back"
when the reader's question is "why did my arrow key scroll".

**Quiet in the stroke, not in the colour.** A paler grey was tried first and is
wrong: `--rule-strong` measures 2.3 and 2.7 to 1 against the row it sits on, in
the two themes, under the 3:1 a state indicator owes (WCAG 1.4.11), and a mark
saying "the way back is here" may not be the faintest thing on the screen.
`--ink-soft` holds 5.4 and 6.2, and one dashed hair against two solid is
already the whole difference.

**ArrowLeft only from the panel itself.** Once the reader has tabbed on to a
link, or into a table that scrolls sideways (0014), that key is theirs. Up and
Down are left alone throughout: on a type page past the fold they are how it is
read. Escape remains the way back from anywhere.

**`--focus` apart from `--link`.** A link is read; a ring is glanced at. At the
link's strength the ring measured 6.5 and 8.4 to 1 against the page and shouted
on every keystroke. `--focus` carries it at roughly 4, which keeps WCAG 2.4.11's
3:1 with room on the tightest ground it meets — the `--field` tint of the
selected row the cursor stands on, where it measures 3.7 and 3.9. The next step
quieter, `#5c8cc4` / `#456f99`, lands at 3.17 and 3.04 there, which is the line
itself and not a margin.

## Consequences

Five rules moved from `--link` to `--focus`: the global `:focus-visible`, the
two tip-bearing terms, the search field and the tree row. Links are unaffected.

Held in a browser by `tests/test_viewer_keyboard.py` (0011): the stroke goes
`solid 2px` → `dashed 1px` → `solid 2px` across Enter and Escape; ArrowLeft
returns to the row Enter was pressed on and not to its parent; ArrowLeft on a
focused link inside the panel is left to the panel; and the ring clears 3:1 in
both themes against the page and against the row, the translucent tint
composited first, since a ratio against an `rgba()` is a ratio against a colour
nobody sees.
