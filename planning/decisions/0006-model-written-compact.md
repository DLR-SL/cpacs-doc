# 0006 — The model is written without indentation

Date: 2026-08-23

## Context

The model was written with two-space indentation, at 15 MB. Compact it is
3.8 MB. It is deployed alongside the site and fetched by the viewer.

## Decision

Written compact.

## Rationale

It is a generated artefact that is parsed, not read. Indentation costs a factor
of four in transfer size for a readability nobody uses; `jq` covers inspection.

## Consequences

The file is not diffable by line. Comparing two model versions is a job for the
diff feature (F18), which compares structure rather than text.
