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
   * top down, a box stands at the top of its subtree and its children are
   * stacked from there: XSDDiagram's Top alignment, the only one offered, so
   * every reader sees the same picture. A compositor that is its parent's only
   * child is centred on the parent, as in XSDDiagram. A depth is a column as wide as
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
      var parent = box.parent;
      if (box.item.kind === "group" && parent && parent.children.length === 1) {
        // The one exception to Top: a compositor alone under its parent is
        // centred on the parent's box, so the connector runs straight.
        box.y = parent.y + (parent.h - box.h) / 2;
      } else {
        box.y = top;
      }
      var cursor = top;
      for (var i = 0; i < box.children.length; i++) {
        place(box.children[i], cursor, columns);
        cursor += box.children[i].span + ROW_GAP;
      }
    }

    if (!root) return { boxes: [], width: 0, height: 0, columns: [] };
    var top = collect(root, 0, null);
    var columns = [0];
    for (var d = 0; d < widths.length; d++) {
      columns[d + 1] = columns[d] + widths[d] + COLUMN_GAP;
    }
    measureSpan(top);
    place(top, 0, columns);

    // Nothing should sit above the top; kept as a guard for the geometry.
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


  /* ---- drawing ---- */

  var SVG_NS = "http://www.w3.org/2000/svg";

  function svg(tag, attributes, parent) {
    var node = document.createElementNS(SVG_NS, tag);
    for (var name in attributes) {
      if (Object.prototype.hasOwnProperty.call(attributes, name)) {
        node.setAttribute(name, attributes[name]);
      }
    }
    if (parent) parent.appendChild(node);
    return node;
  }

  // The bounds as XSDDiagram writes them under a box. Nothing for 1..1, which
  // an unmarked box already says.
  function cardinality(item) {
    if (item.min === 1 && item.max === 1) return "";
    return item.min + ".." + (item.max === null ? "\u221E" : item.max);
  }

  function isRepeated(item) {
    return item.max === null || item.max > 1;
  }

  // XSDDiagram's compositor box: a rectangle with its corners bevelled by
  // 30 % of its height.
  function octagon(x, y, w, h) {
    var b = Math.round(h * 0.3);
    return "M" + (x + b) + " " + y + "H" + (x + w - b)
      + "L" + (x + w) + " " + (y + b) + "V" + (y + h - b)
      + "L" + (x + w - b) + " " + (y + h) + "H" + (x + b)
      + "L" + x + " " + (y + h - b) + "V" + (y + b) + "Z";
  }

  // The three symbols, after XSDDiagram's own: a line with three beads for a
  // sequence, a switch for a choice, brackets for all.
  function drawSymbol(parent, compositor, cx, cy) {
    var d;
    var dots;
    if (compositor === "sequence") {
      d = "M" + (cx - 12) + " " + cy + "H" + (cx + 12);
      dots = [[cx - 5, cy], [cx, cy], [cx + 5, cy]];
    } else if (compositor === "choice") {
      d = "M" + (cx - 12) + " " + cy + "H" + (cx - 8) + "L" + (cx - 4) + " " + (cy - 4)
        + "M" + (cx + 4) + " " + (cy - 4) + "H" + (cx + 8)
        + "M" + (cx + 4) + " " + cy + "H" + (cx + 12)
        + "M" + (cx + 4) + " " + (cy + 4) + "H" + (cx + 8)
        + "M" + (cx + 8) + " " + (cy - 4) + "V" + (cy + 4);
      dots = [[cx, cy - 4], [cx, cy], [cx, cy + 4]];
    } else {
      d = "M" + (cx - 4) + " " + (cy - 4) + "H" + (cx - 8) + "V" + (cy + 4) + "H" + (cx - 4)
        + "M" + (cx - 12) + " " + cy + "H" + (cx - 8)
        + "M" + (cx + 4) + " " + (cy - 4) + "H" + (cx + 8) + "V" + (cy + 4) + "H" + (cx + 4)
        + "M" + (cx + 8) + " " + cy + "H" + (cx + 12);
      dots = [[cx, cy - 4], [cx, cy], [cx, cy + 4]];
    }
    svg("path", { "class": "cd-dg-symbol-line", d: d }, parent);
    for (var i = 0; i < dots.length; i++) {
      svg("circle", { "class": "cd-dg-symbol-dot", cx: dots[i][0], cy: dots[i][1], r: 1.6 }, parent);
    }
  }

  function drawExpander(parent, cx, cy, open) {
    var group = svg("g", { "class": "cd-dg-expander" }, parent);
    svg("rect", {
      x: cx - EXPANDER / 2, y: cy - EXPANDER / 2, width: EXPANDER, height: EXPANDER
    }, group);
    var d = "M" + (cx - 3) + " " + cy + "H" + (cx + 3);
    if (!open) d += "M" + cx + " " + (cy - 3) + "V" + (cy + 3);
    svg("path", { d: d }, group);
  }

  /* ---- the mounted diagram ---- */

  function mount(container, api) {
    var shape = structure(api.model);
    var open = {};            // key -> true for every expanded element
    var selectedKey = null;
    var selectedPath = null;  // the path the viewer was last told of
    var cursorKey = null;
    var view = { scale: 1, x: MARGIN, y: MARGIN };
    var current = null;       // the last layout
    var byKey = {};           // key -> box of the last layout
    var widthCache = {};

    container.textContent = "";
    if (!shape.root) {
      var empty = document.createElement("p");
      empty.className = "cd-empty";
      empty.textContent = "The model contains no tree.";
      container.appendChild(empty);
      return {
        show: function () { return false; },
        focus: function () {},
        view: function () { return { scale: 1, x: 0, y: 0 }; }
      };
    }

    var canvas = svg("svg", {
      "class": "cd-dg-svg", role: "tree", "aria-label": "Instance diagram"
    }, container);
    var probe = svg("text", { "class": "cd-dg-probe", x: -1000, y: -1000 }, canvas);
    var viewport = svg("g", { "class": "cd-dg-view" }, canvas);
    var linkLayer = svg("g", { "class": "cd-dg-links" }, viewport);
    var itemLayer = svg("g", { "class": "cd-dg-items" }, viewport);

    open[shape.root.key] = true;
    cursorKey = shape.root.key;

    // A pane that is not laid out measures nothing. The estimate keeps the
    // boxes readable until the next render measures for real, and is not
    // cached, so that render does.
    function textWidth(text, className) {
      var id = className + "\u0000" + text;
      if (widthCache[id] !== undefined) return widthCache[id];
      probe.setAttribute("class", "cd-dg-probe " + className);
      probe.textContent = text;
      var width = probe.getComputedTextLength ? probe.getComputedTextLength() : 0;
      if (!width) return text.length * 7.5;
      widthCache[id] = width;
      return width;
    }

    function typeLine(item) {
      return item.kind === "element" && item.type ? api.typeRef(item.type) : null;
    }

    function measure(item) {
      if (item.kind === "group") return { w: GROUP_W, h: GROUP_H };
      var ref = typeLine(item);
      var w = textWidth(item.name, "cd-dg-name");
      if (ref) w = Math.max(w, textWidth(ref.label, "cd-dg-type-text"));
      // The expander sits on the right edge, half inside the box.
      return { w: Math.ceil(w) + 2 * PAD_X + EXPANDER / 2, h: ref ? LINE_TWO : LINE_ONE };
    }

    function isOpen(item) {
      return item.kind === "group" || (item.expandable && !!open[item.key]);
    }

    function applyView() {
      viewport.setAttribute(
        "transform", "translate(" + view.x + " " + view.y + ") scale(" + view.scale + ")"
      );
    }

    function level(box) {
      var count = 1;
      for (var p = box.parent; p; p = p.parent) if (p.item.kind === "element") count++;
      return count;
    }

    function connector(box) {
      var cy = box.y + box.h / 2;
      var from = box.x + box.w + (box.item.kind === "element" ? EXPANDER / 2 : 0);
      var bus = current.columns[box.depth + 1] - COLUMN_GAP / 2;
      var top = cy;
      var bottom = cy;
      var d = "M" + from + " " + cy + "H" + bus;
      for (var i = 0; i < box.children.length; i++) {
        var child = box.children[i];
        var middle = child.y + child.h / 2;
        top = Math.min(top, middle);
        bottom = Math.max(bottom, middle);
        d += "M" + bus + " " + middle + "H" + child.x;
      }
      return d + "M" + bus + " " + top + "V" + bottom;
    }

    // The keys from the root to `key`: the route an instance takes to reach
    // it. Keys are positions, so every prefix of a key is an ancestor.
    function routeOf(key) {
      var route = {};
      if (!key || !byKey[key]) return route;
      var parts = key.split(".");
      for (var i = 1; i <= parts.length; i++) route[parts.slice(0, i).join(".")] = true;
      return route;
    }

    // One line per step of the route, parent to child, drawn over the plain
    // connectors so the way reads without the siblings' branches.
    function routeLinks(route) {
      var d = "";
      for (var i = 0; i < current.boxes.length; i++) {
        var child = current.boxes[i];
        var parent = child.parent;
        if (!parent || !route[child.item.key]) continue;
        var from = parent.x + parent.w + (parent.item.kind === "element" ? EXPANDER / 2 : 0);
        var bus = current.columns[parent.depth + 1] - COLUMN_GAP / 2;
        d += "M" + from + " " + (parent.y + parent.h / 2) + "H" + bus
          + "V" + (child.y + child.h / 2) + "H" + child.x;
      }
      return d;
    }

    function drawItem(box, route) {
      var item = box.item;
      var x = box.x;
      var y = box.y;
      var w = box.w;
      var h = box.h;
      var classes = "cd-dg-item cd-dg-" + item.kind;
      if (item.min === 0) classes += " cd-dg-optional";
      if (isRepeated(item)) classes += " cd-dg-repeated";
      if (item.key === selectedKey) classes += " cd-dg-selected";
      else if (route[item.key]) classes += " cd-dg-on-trail";
      if (item.key === cursorKey) classes += " cd-dg-cursor";
      var g = svg("g", { "class": classes, "data-key": item.key }, itemLayer);

      if (item.kind === "group") {
        g.setAttribute("data-compositor", item.compositor);
        svg("title", {}, g).textContent = api.gloss(item.compositor);
        if (isRepeated(item)) {
          svg("path", { "class": "cd-dg-shadow", d: octagon(x + STACK, y + STACK, w, h) }, g);
        }
        svg("path", { "class": "cd-dg-frame", d: octagon(x, y, w, h) }, g);
        drawSymbol(g, item.compositor, x + w / 2, y + h / 2);
      } else {
        if (isRepeated(item)) {
          svg("rect", { "class": "cd-dg-shadow", x: x + STACK, y: y + STACK, width: w, height: h }, g);
        }
        svg("rect", { "class": "cd-dg-frame", x: x, y: y, width: w, height: h }, g);
        // Around the stacked frame too, so the ring never cuts through it.
        var stacked = isRepeated(item) ? STACK : 0;
        svg("rect", {
          "class": "cd-dg-ring", x: x - 4, y: y - 4,
          width: w + 8 + stacked, height: h + 8 + stacked, rx: 3
        }, g);
        svg("text", { "class": "cd-dg-name", x: x + PAD_X, y: y + 15 }, g).textContent = item.name;
      }

      if (item.kind === "element") {
        g.setAttribute("data-path", item.path.join("/"));
        var ref = typeLine(item);
        if (ref) {
          var holder = g;
          if (ref.link) {
            // tabindex -1: Chrome puts an SVG link into the Tab order, and the
            // cursor box is to be the only stop (spec 5.3).
            holder = svg("a", { "class": "cd-dg-type", "data-type": item.type, tabindex: "-1" }, g);
            if (ref.href) holder.setAttribute("href", ref.href);
          }
          svg("text", { "class": "cd-dg-type-text", x: x + PAD_X, y: y + 28 }, holder)
            .textContent = ref.label;
        }
        if (item.selectable) {
          g.setAttribute("role", "treeitem");
          g.setAttribute("aria-level", String(level(box)));
          g.setAttribute("aria-selected", String(item.key === selectedKey));
          g.setAttribute("aria-label", item.name);
          g.setAttribute("tabindex", item.key === cursorKey ? "0" : "-1");
          if (item.expandable) g.setAttribute("aria-expanded", String(!!open[item.key]));
        }
        if (item.expandable) {
          drawExpander(g, x + w, y + h / 2, !!open[item.key]);
        } else if (item.recursive) {
          var mark = svg("text", { "class": "cd-dg-recursive", x: x + w + 3, y: y + h / 2 + 4 }, g);
          mark.textContent = "\u21BB";
          svg("title", {}, mark).textContent =
            "This type already appears further up this path; open it there.";
        }
      }

      var card = cardinality(item);
      if (card) {
        svg("text", {
          "class": "cd-dg-card", x: x + w, y: y + h + STACK + 10, "text-anchor": "end"
        }, g).textContent = card;
      }
    }

    // Every box is drawn anew, the focused one included, so the keyboard is
    // handed back to the cursor if it was in the drawing before.
    function draw() {
      var hadFocus = canvas.contains(document.activeElement);
      linkLayer.textContent = "";
      itemLayer.textContent = "";
      var route = routeOf(selectedKey);
      var d = "";
      for (var i = 0; i < current.boxes.length; i++) {
        var box = current.boxes[i];
        if (box.children.length) d += connector(box);
        drawItem(box, route);
      }
      svg("path", { "class": "cd-dg-link", d: d }, linkLayer);
      svg("path", { "class": "cd-dg-link cd-dg-trail-link", d: routeLinks(route) }, linkLayer);
      hoverLink = svg("path", { "class": "cd-dg-link cd-dg-hover-link", d: "" }, linkLayer);
      hoverKey = null;
      if (hadFocus) focus();
    }

    // The route of the box under the pointer, as a lighter preview of what a
    // click would mark. Classes are toggled on the few boxes of one route
    // rather than the drawing redrawn.
    var hoverLink = null;
    var hoverKey = null;

    function preview(key) {
      hoverKey = key;
      var marked = itemLayer.querySelectorAll(".cd-dg-hover-trail");
      for (var i = 0; i < marked.length; i++) marked[i].classList.remove("cd-dg-hover-trail");
      var route = routeOf(key);
      hoverLink.setAttribute("d", routeLinks(route));
      for (var k in route) {
        if (!Object.prototype.hasOwnProperty.call(route, k)) continue;
        var node = itemLayer.querySelector('[data-key="' + k + '"]');
        if (node) node.classList.add("cd-dg-hover-trail");
      }
    }

    // The nearest drawn ancestor of a key that is no longer drawn: keys are
    // positions, so an ancestor's key is a prefix.
    function drawnKey(key) {
      while (key && !byKey[key]) {
        var cut = key.lastIndexOf(".");
        key = cut === -1 ? null : key.slice(0, cut);
      }
      return key || shape.root.key;
    }

    // Lays out again and draws. `anchorKey` names a box that must not move on
    // screen — the one just opened or closed.
    function render(anchorKey) {
      var anchor = anchorKey && byKey[anchorKey] ? byKey[anchorKey] : null;
      var before = anchor
        ? { x: view.x + anchor.x * view.scale, y: view.y + anchor.y * view.scale }
        : null;
      current = layout(shape.root, shape.children, isOpen, measure);
      byKey = {};
      for (var i = 0; i < current.boxes.length; i++) byKey[current.boxes[i].item.key] = current.boxes[i];
      if (before && byKey[anchorKey]) {
        view.x = before.x - byKey[anchorKey].x * view.scale;
        view.y = before.y - byKey[anchorKey].y * view.scale;
      }
      cursorKey = drawnKey(cursorKey);
      draw();
      applyView();
    }

    function toggle(item) {
      if (!item.expandable) return;
      if (open[item.key]) delete open[item.key];
      else open[item.key] = true;
      render(item.key);
    }

    function choose(item, focusDetail) {
      if (!item.selectable) return;
      selectedKey = item.key;
      selectedPath = item.path.join("/");
      cursorKey = item.key;
      draw();
      api.select(item.path, focusDetail);
    }

    function visibleWidth() {
      return Math.max(0, canvas.clientWidth - (api.covered ? api.covered() : 0));
    }

    // Pans the box into the part of the pane the reader can see: always to
    // its middle with `always`, otherwise only when it is not wholly in view.
    function reveal(box, always) {
      if (!box) return;
      var width = visibleWidth();
      var height = canvas.clientHeight;
      var s = view.scale;
      var left = view.x + box.x * s;
      var top = view.y + box.y * s;
      var inside = left >= MARGIN && top >= MARGIN
        && left + box.w * s <= width - MARGIN && top + box.h * s <= height - MARGIN;
      if (inside && !always) return;
      view.x = width / 2 - (box.x + box.w / 2) * s;
      view.y = height / 2 - (box.y + box.h / 2) * s;
      applyView();
    }

    function show(path, centre) {
      var chain = shape.find(path);
      if (!chain) {
        // No box is selected any more; the old mark would contradict "Not found".
        selectedKey = null;
        selectedPath = null;
        render(null);
        return false;
      }
      for (var i = 0; i < chain.length - 1; i++) open[chain[i].key] = true;
      var wanted = path.join("/");
      // The box the reader clicked keeps the mark when the viewer answers
      // with the same path, even where another box shares it.
      if (selectedPath !== wanted || !selectedKey) {
        selectedKey = chain[chain.length - 1].key;
        selectedPath = wanted;
      }
      cursorKey = selectedKey;
      render(null);
      reveal(byKey[selectedKey], !!centre);
      return true;
    }

    function focus() {
      var node = itemLayer.querySelector('[data-key="' + cursorKey + '"]');
      if (node && node.focus) node.focus({ preventScroll: true });
    }

    canvas.addEventListener("click", function (event) {
      var itemNode = event.target.closest(".cd-dg-item");
      if (!itemNode) return;
      var box = byKey[itemNode.getAttribute("data-key")];
      if (!box) return;
      if (event.target.closest(".cd-dg-expander")) {
        toggle(box.item);
        return;
      }
      var link = event.target.closest(".cd-dg-type");
      if (link) {
        // A modified click is the reader asking for the page itself; the
        // browser follows the href. A plain one keeps the diagram and shows
        // the type beside it, the bargain `typeCell` makes in the tables.
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) return;
        event.preventDefault();
        choose(box.item, false);
        api.showType(link.getAttribute("data-type"));
        return;
      }
      choose(box.item, false);
    });

    canvas.addEventListener("mouseover", function (event) {
      var node = event.target.closest(".cd-dg-item");
      var key = node ? node.getAttribute("data-key") : null;
      if (key !== hoverKey) preview(key);
    });
    canvas.addEventListener("mouseleave", function () {
      if (hoverKey !== null) preview(null);
    });

    canvas.addEventListener("dblclick", function (event) {
      var itemNode = event.target.closest(".cd-dg-item");
      if (!itemNode || event.target.closest(".cd-dg-expander")) return;
      var box = byKey[itemNode.getAttribute("data-key")];
      if (box) toggle(box.item);
    });

    /* ---- zoom and pan ---- */

    // The point under (px, py) stays where it is.
    function scaleAt(next, px, py) {
      view.x = px - (px - view.x) * next / view.scale;
      view.y = py - (py - view.y) * next / view.scale;
      view.scale = next;
      applyView();
    }

    function zoomAt(factor, px, py) {
      scaleAt(Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, view.scale * factor)), px, py);
    }

    // Around the middle of what the reader can see, which is left of the
    // overlay while it is open.
    function zoomBy(factor) {
      zoomAt(factor, visibleWidth() / 2, canvas.clientHeight / 2);
    }

    // Exactly the scale asked for, not a product of factors that lands a
    // rounding error beside it.
    function setScale(scale) {
      scaleAt(scale, visibleWidth() / 2, canvas.clientHeight / 2);
    }

    function fit() {
      var width = visibleWidth();
      var height = canvas.clientHeight;
      var scale = Math.min(
        (width - 2 * MARGIN) / current.width, (height - 2 * MARGIN) / current.height, 1
      );
      view.scale = Math.max(ZOOM_MIN, scale);
      view.x = (width - current.width * view.scale) / 2;
      view.y = (height - current.height * view.scale) / 2;
      applyView();
    }

    // Not passive: an unhandled Ctrl+wheel is the browser zooming the whole
    // page, which is the one thing this gesture must not do here.
    canvas.addEventListener("wheel", function (event) {
      var rect = canvas.getBoundingClientRect();
      if (event.ctrlKey) {
        zoomAt(Math.exp(-event.deltaY * 0.002), event.clientX - rect.left, event.clientY - rect.top);
      } else if (event.shiftKey) {
        view.x -= event.deltaY || event.deltaX;
        applyView();
      } else {
        view.x -= event.deltaX;
        view.y -= event.deltaY;
        applyView();
      }
      event.preventDefault();
    }, { passive: false });

    // Dragging starts only on the canvas itself; on a box a press is a click.
    var drag = null;
    canvas.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest(".cd-dg-item")) return;
      drag = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
      if (canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!drag) return;
      view.x = drag.viewX + event.clientX - drag.x;
      view.y = drag.viewY + event.clientY - drag.y;
      applyView();
    });
    function endDrag() { drag = null; }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    var toolbar = document.createElement("div");
    toolbar.className = "cd-dg-toolbar";
    [
      ["cd-dg-zoom-out", "\u2212", "Zoom out", function () { zoomBy(0.8); }],
      ["cd-dg-zoom-in", "+", "Zoom in", function () { zoomBy(1.25); }],
      ["cd-dg-zoom-reset", "100 %", "Actual size", function () { setScale(1); }],
      ["cd-dg-fit", "Fit", "Fit the diagram into the window", fit],
      ["cd-dg-centre", "Centre", "Centre the selection",
        function () { reveal(byKey[selectedKey] || byKey[cursorKey], true); }]
    ].forEach(function (spec) {
      var button = document.createElement("button");
      button.type = "button";
      button.id = spec[0];
      button.textContent = spec[1];
      button.title = spec[2];
      button.setAttribute("aria-label", spec[2]);
      button.addEventListener("click", spec[3]);
      toolbar.appendChild(button);
    });
    container.appendChild(toolbar);

    /* ---- keyboard (0010, 0016-0021, in two dimensions) ---- */

    function isTarget(box) {
      return box.item.kind === "element" && box.item.selectable;
    }

    function parentElement(box) {
      var p = box.parent;
      while (p && p.item.kind !== "element") p = p.parent;
      return p;
    }

    // The boxes are in depth-first order, so the children of one element
    // stand in them top to bottom.
    function siblings(box) {
      var parent = parentElement(box);
      if (!parent) return [box];
      return current.boxes.filter(function (b) { return isTarget(b) && parentElement(b) === parent; });
    }

    function firstChild(box) {
      for (var i = 0; i < current.boxes.length; i++) {
        var b = current.boxes[i];
        if (isTarget(b) && parentElement(b) === box) return b;
      }
      return null;
    }

    // Siblings first; past the last of them, the nearest box of the same
    // column in that direction — the column is what the eye runs down.
    function vertical(box, step) {
      var list = siblings(box);
      var index = list.indexOf(box);
      if (list[index + step]) return list[index + step];
      var best = null;
      for (var i = 0; i < current.boxes.length; i++) {
        var b = current.boxes[i];
        if (b === box || !isTarget(b) || b.depth !== box.depth) continue;
        var ahead = step > 0 ? b.y > box.y : b.y < box.y;
        if (ahead && (!best || Math.abs(b.y - box.y) < Math.abs(best.y - box.y))) best = b;
      }
      return best;
    }

    function columnEnd(box, step) {
      var column = current.boxes.filter(function (b) { return isTarget(b) && b.depth === box.depth; });
      column.sort(function (a, b) { return a.y - b.y; });
      return step < 0 ? column[0] : column[column.length - 1];
    }

    function moveTo(target) {
      if (!target) return;
      cursorKey = target.item.key;
      draw();
      focus();
      reveal(target, false);
    }

    canvas.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      var box = byKey[cursorKey];
      if (!box) return;
      var item = box.item;
      switch (event.key) {
        case "ArrowDown": moveTo(vertical(box, 1)); break;
        case "ArrowUp": moveTo(vertical(box, -1)); break;
        case "ArrowRight":
          if (item.expandable && !open[item.key]) toggle(item);
          else moveTo(firstChild(box));
          break;
        case "ArrowLeft":
          if (item.expandable && open[item.key]) toggle(item);
          else moveTo(parentElement(box));
          break;
        case "Home": moveTo(columnEnd(box, -1)); break;
        case "End": moveTo(columnEnd(box, 1)); break;
        case " ": choose(item, false); break;
        case "Enter": choose(item, true); break;
        case "+": case "=": zoomBy(1.25); break;
        case "-": zoomBy(0.8); break;
        case "0": setScale(1); break;
        default: return;
      }
      event.preventDefault();
    });

    render(null);

    return {
      show: show,
      focus: focus,
      view: function () { return { scale: view.scale, x: view.x, y: view.y }; }
    };
  }

  window.CpacsDiagram = {
    structure: structure,
    layout: layout,
    mount: mount
  };
})();
