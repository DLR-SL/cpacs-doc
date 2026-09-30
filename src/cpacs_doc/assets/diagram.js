/* The instance tree, drawn the way XSDDiagram draws it
 * (planning/specs/2026-09-30-diagram-view-design.md).
 *
 * A second view of the model the tree shows: boxes left to right, the
 * compositors as symbols between them, children expanded on demand. The module
 * knows nothing of URLs, tabs or the detail panel; the viewer lends it what it
 * needs through `api` and hears back through `api.select` and `api.showType`.
 *
 * `structure` and `layout` are pure and exported, so the browser tests can hold
 * them to their contract without drawing anything.
 */
(function () {
  "use strict";

  window.CpacsDiagram = {};
})();
