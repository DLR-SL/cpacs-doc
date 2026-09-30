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

  // Geometry, in diagram units: pixels at 100 %.
  var PAD_X = 8;           // text inset inside a box
  var LINE_ONE = 22;       // a box holding the name alone
  var LINE_TWO = 34;       // a box holding the name and the type under it
  var GROUP_W = 34;
  var GROUP_H = 18;
  var EXPANDER = 10;       // side of the +/- square, centred on the right edge
  var STACK = 3;           // offset of the second frame behind a repeated item
  var CARD_ROOM = 12;      // room under a box for its cardinality
  var COLUMN_GAP = 30;     // from the widest box of a column to the next column
  var ROW_GAP = 8;         // between sibling subtrees
  var MARGIN = 24;         // between the drawing and the edge of the pane
  var ZOOM_MIN = 0.25;
  var ZOOM_MAX = 2;

  function bound(value) {
    return value === undefined ? 1 : value;
  }

  /* ---- structure ----
   *
   * `model.tree` holds the elements and nothing else. The compositors are in
   * the member list of each element's type, so the diagram walks that list and
   * claims, for every element member, the tree child declared on the same line
   * under the same name. Groups and `any` have no tree node and are built from
   * the member alone.
   *
   * An element opens when its type has members, not when its tree node has
   * children: content that is only `xsd:any` has no tree child and still has
   * something to show. A recursive node does not open, as in the tree.
   */
  function structure(model) {
    var types = model.types || {};
    var declarations = model.declarations || {};

    function declarationOf(node) {
      return declarations[node.d] || {};
    }

    function membersOf(typeName) {
      var type = typeName ? types[typeName] : null;
      return type && type.children ? type.children : [];
    }

    function elementItem(node, decl, path, key) {
      var members = node && !node.recursive ? membersOf(decl.type) : [];
      return {
        key: key,
        kind: "element",
        node: node,
        name: decl.name || "?",
        type: decl.type || null,
        min: bound(decl.minOccurs),
        max: bound(decl.maxOccurs),
        path: path,
        // A member no tree node answers to has no path the viewer can show.
        selectable: !!node,
        recursive: !!(node && node.recursive),
        expandable: members.length > 0,
        members: members,
        children: null
      };
    }

    function claim(pool, member) {
      for (var i = 0; i < pool.length; i++) {
        var decl = declarationOf(pool[i]);
        if (decl.line === member.line && decl.name === member.name) {
          return pool.splice(i, 1)[0];
        }
      }
      return null;
    }

    function convert(members, owner, pool, prefix) {
      var out = [];
      for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var key = prefix + "." + i;
        if (member.kind === "group") {
          var group = {
            key: key,
            kind: "group",
            compositor: member.compositor,
            min: bound(member.minOccurs),
            max: bound(member.maxOccurs),
            selectable: false,
            expandable: false,
            children: null
          };
          group.children = convert(member.members || [], owner, pool, key);
          out.push(group);
        } else if (member.kind === "element") {
          var node = claim(pool, member);
          out.push(elementItem(
            node, node ? declarationOf(node) : member, owner.path.concat(member.name), key
          ));
        } else {
          out.push({
            key: key,
            kind: "any",
            name: "any",
            min: bound(member.minOccurs),
            max: bound(member.maxOccurs),
            selectable: false,
            expandable: false,
            children: []
          });
        }
      }
      return out;
    }

    // Built once per item and kept: the keys are positions, and they have to
    // mean the same box on every render.
    function children(item) {
      if (item.children) return item.children;
      if (item.kind !== "element" || !item.expandable) {
        item.children = [];
        return item.children;
      }
      var pool = (item.node.children || []).slice();
      item.children = convert(item.members, item, pool, item.key);
      return item.children;
    }

    // The elements an element contains, looking through its compositors.
    function elementChildren(item) {
      var out = [];
      (function walk(list) {
        for (var i = 0; i < list.length; i++) {
          if (list[i].kind === "group") walk(list[i].children);
          else if (list[i].kind === "element") out.push(list[i]);
        }
      })(children(item));
      return out;
    }

    // Where two elements share a path — the branches of a choice may — the
    // first one found wins, as it does in the tree's index.
    function find(path) {
      if (!root) return null;
      var chain = [root];
      var item = root;
      for (var i = 0; i < path.length; i++) {
        var candidates = elementChildren(item);
        var next = null;
        for (var j = 0; j < candidates.length; j++) {
          if (candidates[j].name === path[i]) {
            next = candidates[j];
            break;
          }
        }
        if (!next) return null;
        chain.push(next);
        item = next;
      }
      return chain;
    }

    var root = model.tree
      ? elementItem(model.tree, declarationOf(model.tree), [], "0")
      : null;
    return { root: root, children: children, elementChildren: elementChildren, find: find };
  }

  /* ---- layout ----
   *
   * XSDDiagram's tidy tree, over the visible items only. Bottom up, a subtree
   * is as tall as its children together, and at least as tall as its own box;
   * top down, a box is centred on its children. A depth is a column as wide as
   * its widest box, so boxes of one depth line up — calmer than XSDDiagram's
   * per-box indent, and the column is what the keyboard moves along.
   */
  function layout(root, children, isOpen, measure) {
    var boxes = [];
    var widths = [];

    function collect(item, depth, parent) {
      var size = measure(item);
      var box = {
        item: item, depth: depth, parent: parent, children: [],
        x: 0, y: 0, w: size.w, h: size.h,
        slot: size.h + CARD_ROOM + STACK, span: 0, inner: 0
      };
      boxes.push(box);
      widths[depth] = Math.max(widths[depth] || 0, size.w);
      if (isOpen(item)) {
        var list = children(item);
        for (var i = 0; i < list.length; i++) {
          box.children.push(collect(list[i], depth + 1, box));
        }
      }
      return box;
    }

    function measureSpan(box) {
      var sum = 0;
      for (var i = 0; i < box.children.length; i++) {
        sum += measureSpan(box.children[i]) + (i ? ROW_GAP : 0);
      }
      box.inner = sum;
      box.span = Math.max(box.slot, sum);
      return box.span;
    }

    function place(box, top, columns) {
      box.x = columns[box.depth];
      if (!box.children.length) {
        box.y = top + (box.span - box.slot) / 2;
        return;
      }
      var cursor = top + (box.span - box.inner) / 2;
      for (var i = 0; i < box.children.length; i++) {
        place(box.children[i], cursor, columns);
        cursor += box.children[i].span + ROW_GAP;
      }
      var first = box.children[0];
      var last = box.children[box.children.length - 1];
      var middle = (first.y + first.h / 2 + last.y + last.h / 2) / 2;
      box.y = middle - box.h / 2;
    }

    if (!root) return { boxes: [], width: 0, height: 0, columns: [] };
    var top = collect(root, 0, null);
    var columns = [0];
    for (var d = 0; d < widths.length; d++) {
      columns[d + 1] = columns[d] + widths[d] + COLUMN_GAP;
    }
    measureSpan(top);
    place(top, 0, columns);

    // Centring a tall parent on short children can lift it above the top.
    var least = 0;
    var height = 0;
    for (var i = 0; i < boxes.length; i++) least = Math.min(least, boxes[i].y);
    for (var j = 0; j < boxes.length; j++) {
      boxes[j].y -= least;
      height = Math.max(height, boxes[j].y + boxes[j].slot);
    }
    var last = widths.length - 1;
    return {
      boxes: boxes,
      width: columns[last] + widths[last] + STACK + EXPANDER,
      height: height,
      columns: columns
    };
  }

  window.CpacsDiagram = {
    structure: structure,
    layout: layout
  };
})();
