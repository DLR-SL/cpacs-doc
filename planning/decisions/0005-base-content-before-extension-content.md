# 0005 — Inherited content is listed before a type's own

Date: 2026-08-23

## Context

Where a type extends another, an instance carries the base type's elements
before the extension's. Both the tree and the child table originally listed the
type's own content first.

## Decision

Base content first, in the tree and on type pages alike. Attributes keep the
opposite order, nearest declaration first, because a derived type may narrow an
inherited attribute and the nearest declaration is the one an instance sees.

## Rationale

The tree mirrors an instance; showing an order no instance ever has would
mislead. In CPACS the effect is currently invisible, because `complexBaseType`
contributes only attributes and no child elements — which is precisely why it
went unnoticed.

## Consequences

Two orderings coexist in the same module, and the reason is recorded there.
