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
  var GROUP_W = 36;
  var GROUP_H = 18;
  var EXPANDER = 10;       // side of the +/- square, centered on the right edge
  var STACK = 3;           // offset of the second frame behind a repeated item
  var CARD_ROOM = 12;      // room under a box for its cardinality
  var COLUMN_GAP = 20;     // from a box to the column of its children
  var ROW_GAP = 9;         // between sibling subtrees
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
   * child is centered on the parent, as in XSDDiagram. Children start just
   * past their own parent, again as XSDDiagram does: aligning every depth
   * across the whole drawing let one long name stretch every branch.
   */
  function layout(root, children, isOpen, measure) {
    var boxes = [];

    function collect(item, depth, parent) {
      var size = measure(item);
      var box = {
        item: item, depth: depth, parent: parent, children: [],
        x: 0, y: 0, w: size.w, h: size.h,
        // The room under the box: what `measure` says stands there, or, from
        // a measure that does not say, room for a bound and a stacked frame.
        slot: size.h + (size.below === undefined ? CARD_ROOM + STACK : size.below),
        span: 0, inner: 0
      };
      boxes.push(box);
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

    // Children start just past their own parent, as in XSDDiagram, so one
    // long name widens its own branch and not every branch at its depth.
    function place(box, top) {
      var parent = box.parent;
      box.x = parent ? parent.x + parent.w + COLUMN_GAP : 0;
      if (box.item.kind === "group" && parent && parent.children.length === 1) {
        // The one exception to Top: a compositor alone under its parent is
        // centered on the parent's box, so the connector runs straight.
        box.y = parent.y + (parent.h - box.h) / 2;
      } else {
        box.y = top;
      }
      var cursor = top;
      for (var i = 0; i < box.children.length; i++) {
        place(box.children[i], cursor);
        cursor += box.children[i].span + ROW_GAP;
      }
    }

    if (!root) return { boxes: [], width: 0, height: 0 };
    var top = collect(root, 0, null);
    measureSpan(top);
    place(top, 0);

    // Nothing should sit above the top; kept as a guard for the geometry.
    var least = 0;
    var height = 0;
    var width = 0;
    for (var i = 0; i < boxes.length; i++) least = Math.min(least, boxes[i].y);
    for (var j = 0; j < boxes.length; j++) {
      boxes[j].y -= least;
      height = Math.max(height, boxes[j].y + boxes[j].slot);
      width = Math.max(width, boxes[j].x + boxes[j].w + STACK + EXPANDER);
    }
    return { boxes: boxes, width: width, height: height };
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

  // The bounds as XSDDiagram writes them under a box. The expert view writes
  // every one of them. The default leaves out what the frame already says \u2014
  // 1..1 is a plain frame, 0..1 a dashed one \u2014 and keeps the rest, which the
  // stacked frame of a repeated element only hints at.
  function cardinality(item, expert) {
    var text = item.min + ".." + (item.max === null ? "\u221E" : item.max);
    if (expert) return text;
    return item.max === 1 && item.min <= 1 ? "" : text;
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
  // sequence, a switch for a choice, brackets for all. A little larger than
  // XSDDiagram's, which at 100 % in a browser ran together into a dash, and
  // drawn in the soft ink: they structure the drawing, the names are read.
  function drawSymbol(parent, compositor, cx, cy) {
    var u = 4.5;   // the symbol's grid step
    var d;
    var dots;
    if (compositor === "sequence") {
      d = "M" + (cx - 3 * u) + " " + cy + "H" + (cx + 3 * u);
      dots = [[cx - 5, cy], [cx, cy], [cx + 5, cy]];
    } else if (compositor === "choice") {
      d = "M" + (cx - 3 * u) + " " + cy + "H" + (cx - 2 * u) + "L" + (cx - u) + " " + (cy - u)
        + "M" + (cx + u) + " " + (cy - u) + "H" + (cx + 2 * u)
        + "M" + (cx + u) + " " + cy + "H" + (cx + 3 * u)
        + "M" + (cx + u) + " " + (cy + u) + "H" + (cx + 2 * u)
        + "M" + (cx + 2 * u) + " " + (cy - u) + "V" + (cy + u);
      dots = [[cx, cy - u], [cx, cy], [cx, cy + u]];
    } else {
      d = "M" + (cx - u) + " " + (cy - u) + "H" + (cx - 2 * u) + "V" + (cy + u) + "H" + (cx - u)
        + "M" + (cx - 3 * u) + " " + cy + "H" + (cx - 2 * u)
        + "M" + (cx + u) + " " + (cy - u) + "H" + (cx + 2 * u) + "V" + (cy + u) + "H" + (cx + u)
        + "M" + (cx + 2 * u) + " " + cy + "H" + (cx + 3 * u);
      dots = [[cx, cy - u], [cx, cy], [cx, cy + u]];
    }
    svg("path", { "class": "cd-dg-symbol-line", d: d }, parent);
    for (var i = 0; i < dots.length; i++) {
      svg("circle", { "class": "cd-dg-symbol-dot", cx: dots[i][0], cy: dots[i][1], r: 1.5 }, parent);
    }
  }

  var EXPANDER_HIT = 24;   // the area a click on the expander may land in

  function drawExpander(parent, cx, cy, open) {
    var group = svg("g", { "class": "cd-dg-expander" }, parent);
    // Invisible, and larger than the square it serves: ten pixels are a small
    // target for a mouse and none at all for a finger.
    svg("rect", {
      "class": "cd-dg-hit", x: cx - EXPANDER_HIT / 2, y: cy - EXPANDER_HIT / 2,
      width: EXPANDER_HIT, height: EXPANDER_HIT
    }, group);
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
    // Types and every bound for the reader who needs them; names and the
    // bounds that carry news for everyone else. The viewer remembers it.
    var expert = !!api.expert;

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
      return expert && item.kind === "element" && item.type ? api.typeRef(item.type) : null;
    }

    // Room under a box only for what stands there: its bound, and the
    // stacked frame of a repeated item. Most boxes in the default drawing have
    // neither, and reserving it for all of them spread every column apart.
    function roomBelow(item) {
      return (cardinality(item, expert) ? CARD_ROOM : 0) + (isRepeated(item) ? STACK : 0);
    }

    function measure(item) {
      if (item.kind === "group") return { w: GROUP_W, h: GROUP_H, below: roomBelow(item) };
      var ref = typeLine(item);
      var w = textWidth(item.name, "cd-dg-name");
      if (ref) w = Math.max(w, textWidth(ref.label, "cd-dg-type-text"));
      // The expander sits on the right edge, half inside the box.
      return {
        w: Math.ceil(w) + 2 * PAD_X + EXPANDER / 2,
        h: ref ? LINE_TWO : LINE_ONE,
        below: roomBelow(item)
      };
    }

    function isOpen(item) {
      return item.kind === "group" || (item.expandable && !!open[item.key]);
    }

    var readout = null;   // the zoom button that shows the scale

    function applyView() {
      if (readout) readout.textContent = Math.round(view.scale * 100) + " %";
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
      var bus = box.x + box.w + COLUMN_GAP / 2;
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
        var bus = parent.x + parent.w + COLUMN_GAP / 2;
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

      var card = cardinality(item, expert);
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
      var opening = !open[item.key];
      if (opening) open[item.key] = true;
      else delete open[item.key];
      var before = byKey;
      render(item.key);
      if (opening) markEntered(before);
    }

    // The boxes an expand brought in, so they can arrive rather than appear:
    // twenty boxes at once are otherwise hard to tell from what was there.
    function markEntered(before) {
      for (var key in byKey) {
        if (!Object.prototype.hasOwnProperty.call(byKey, key) || before[key]) continue;
        var node = itemLayer.querySelector('[data-key="' + key + '"]');
        if (node) node.classList.add("cd-dg-enter");
      }
    }

    function deselect() {
      selectedKey = null;
      selectedPath = null;
      draw();
      if (api.deselect) api.deselect();
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

    // Below, where a narrow window shows the documentation as a sheet.
    function visibleHeight() {
      return Math.max(0, canvas.clientHeight - (api.coveredBelow ? api.coveredBelow() : 0));
    }

    // Pans the box into the part of the pane the reader can see: always to
    // its middle with `always`, otherwise only when it is not wholly in view.
    function reveal(box, always) {
      if (!box) return;
      var width = visibleWidth();
      var height = visibleHeight();
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

    // Where reading starts: the chosen box in the upper left of what is
    // visible. With the Top alignment its subtree hangs down and to the right
    // of it, and a centered box left half of the window empty above it.
    // The parent stands whole at the left edge where that keeps the box in
    // the left half, so the reader sees what it hangs from.
    function settle(box) {
      if (!box) return;
      var s = view.scale;
      var width = visibleWidth();
      var left = Math.max(MARGIN, Math.round(width * 0.3));
      var parent = parentElement(box);
      if (parent && MARGIN + (box.x - parent.x) * s < width / 2) {
        left = MARGIN + (box.x - parent.x) * s;
      }
      view.x = left - box.x * s;
      view.y = Math.max(MARGIN, Math.round(visibleHeight() / 6)) - box.y * s;
      applyView();
    }

    // `place` puts the box where reading starts; without it the view only
    // moves when the box is out of sight.
    function show(path, place) {
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
      if (!path.length && selectedPath !== "") {
        // The bare diagram marks nothing, as XSDDiagram does before a click;
        // the root is marked only once the reader has chosen it.
        selectedKey = null;
        selectedPath = null;
      } else if (selectedPath !== wanted || !selectedKey) {
        // The box the reader clicked keeps the mark when the viewer answers
        // with the same path, even where another box shares it.
        selectedKey = chain[chain.length - 1].key;
        selectedPath = wanted;
      }
      cursorKey = selectedKey || shape.root.key;
      render(null);
      if (place) settle(byKey[selectedKey]);
      else if (selectedKey) reveal(byKey[selectedKey], false);
      return true;
    }

    function focus() {
      var node = itemLayer.querySelector('[data-key="' + cursorKey + '"]');
      if (node && node.focus) node.focus({ preventScroll: true });
    }

    canvas.addEventListener("click", function (event) {
      var itemNode = event.target.closest(".cd-dg-item");
      if (!itemNode) {
        // The free canvas takes the selection away, as in XSDDiagram — unless
        // the press was the start of a pan, which ends in a click too.
        if (!panned && selectedKey !== null) deselect();
        return;
      }
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
      zoomAt(factor, visibleWidth() / 2, visibleHeight() / 2);
    }

    // Exactly the scale asked for, not a product of factors that lands a
    // rounding error beside it.
    function setScale(scale) {
      scaleAt(scale, visibleWidth() / 2, visibleHeight() / 2);
    }

    function fit() {
      var width = visibleWidth();
      var height = visibleHeight();
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
    var panned = false;   // whether the last press on the canvas moved it
    canvas.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || event.target.closest(".cd-dg-item")) return;
      panned = false;
      drag = { x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y };
      if (canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!drag) return;
      if (Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y) > 3) panned = true;
      view.x = drag.viewX + event.clientX - drag.x;
      view.y = drag.viewY + event.clientY - drag.y;
      applyView();
    });
    function endDrag() { drag = null; }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    var toolbar = document.createElement("div");
    toolbar.className = "cd-dg-toolbar";

    function toolButton(parent, id, label, title, action) {
      var button = document.createElement("button");
      button.type = "button";
      button.id = id;
      button.textContent = label;
      button.title = title;
      button.setAttribute("aria-label", title);
      button.addEventListener("click", action);
      parent.appendChild(button);
      return button;
    }

    // Out, the scale as it stands, in: one control, read left to right. The
    // middle button says where the zoom is and takes it back to 100 %.
    var zoomGroup = document.createElement("div");
    zoomGroup.className = "cd-dg-joined cd-dg-zoom";
    zoomGroup.setAttribute("role", "group");
    zoomGroup.setAttribute("aria-label", "Zoom");
    toolbar.appendChild(zoomGroup);
    toolButton(zoomGroup, "cd-dg-zoom-out", "\u2212", "Zoom out", function () { zoomBy(0.8); });
    readout = toolButton(zoomGroup, "cd-dg-zoom-reset", "100 %", "Back to 100 %",
      function () { setScale(1); });
    toolButton(zoomGroup, "cd-dg-zoom-in", "+", "Zoom in", function () { zoomBy(1.25); });
    toolButton(toolbar, "cd-dg-fit", "Fit", "Fit the diagram into the window", fit);
    toolButton(toolbar, "cd-dg-center", "Center", "Center the selection",
      function () { reveal(byKey[selectedKey] || byKey[cursorKey], true); });
    applyView();
    // A switch, not an action, so it says whether it is on. Kept apart from
    // the zoom buttons: it changes what is drawn, not where.
    var expertButton = document.createElement("button");
    expertButton.type = "button";
    expertButton.id = "cd-dg-expert";
    expertButton.className = "cd-dg-switch";
    expertButton.textContent = "Expert";
    expertButton.title = "Show every type and every occurrence";
    expertButton.setAttribute("aria-pressed", String(expert));
    expertButton.addEventListener("click", function () { setExpert(!expert); });
    toolbar.appendChild(expertButton);

    // Boxes change their size, so the drawing is laid out again around the
    // chosen box, which stays where the reader was looking.
    function setExpert(on) {
      expert = !!on;
      expertButton.setAttribute("aria-pressed", String(expert));
      render(selectedKey && byKey[selectedKey] ? selectedKey : cursorKey);
      if (api.rememberExpert) api.rememberExpert(expert);
    }

    /* ---- export ----
     *
     * The drawing as it stands — what is expanded, the expert view, the path
     * to the selection — but not the zoom or the pan, which are only the
     * reader's window onto it; nothing is cut off at the window's edge. The
     * styles are written into the elements, because the page's stylesheet and
     * its custom properties do not travel with the file.
     */
    var EXPORTED_STYLES = [
      "fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray",
      "stroke-opacity", "stroke-linecap", "font-family", "font-size",
      "font-weight", "text-decoration", "text-anchor"
    ];

    function exportSize() {
      return {
        w: Math.ceil(current.width + 2 * MARGIN),
        h: Math.ceil(current.height + 2 * MARGIN)
      };
    }

    // `transparent` leaves the ground out; the boxes keep their fill.
    function exportSvg(transparent) {
      var size = exportSize();
      var drawing = viewport.cloneNode(true);
      var sources = viewport.querySelectorAll("*");
      var copies = drawing.querySelectorAll("*");
      for (var i = 0; i < sources.length; i++) {
        var computed = window.getComputedStyle(sources[i]);
        var declarations = [];
        for (var p = 0; p < EXPORTED_STYLES.length; p++) {
          var value = computed.getPropertyValue(EXPORTED_STYLES[p]);
          if (value) declarations.push(EXPORTED_STYLES[p] + ":" + value);
        }
        copies[i].setAttribute("style", declarations.join(";"));
      }
      // The page's machinery: focus rings, click areas, the hover preview.
      var machinery = drawing.querySelectorAll(".cd-dg-ring, .cd-dg-hit, .cd-dg-hover-link");
      for (var m = 0; m < machinery.length; m++) machinery[m].parentNode.removeChild(machinery[m]);
      drawing.setAttribute("transform", "translate(" + MARGIN + " " + MARGIN + ")");

      var file = document.createElementNS(SVG_NS, "svg");
      file.setAttribute("width", String(size.w));
      file.setAttribute("height", String(size.h));
      file.setAttribute("viewBox", "0 0 " + size.w + " " + size.h);
      if (!transparent) {
        svg("rect", {
          width: size.w, height: size.h,
          fill: window.getComputedStyle(document.body).backgroundColor
        }, file);
      }
      file.appendChild(drawing);
      return new XMLSerializer().serializeToString(file);
    }

    // Twice the resolution for a sharp picture, less where a very large
    // drawing would pass what a browser's canvas holds; SVG has no such limit.
    // The ground is transparent, so the picture sits on a slide or a page
    // without a rectangle of the viewer's colour around it.
    function exportPng() {
      var size = exportSize();
      var scale = Math.min(2, 16000 / size.w, 16000 / size.h,
        Math.sqrt(2.5e8 / (size.w * size.h)));
      var url = URL.createObjectURL(new Blob([exportSvg(true)], { type: "image/svg+xml" }));
      return new Promise(function (resolve, reject) {
        var image = new Image();
        image.onload = function () {
          var canvas = document.createElement("canvas");
          canvas.width = Math.floor(size.w * scale);
          canvas.height = Math.floor(size.h * scale);
          var context = canvas.getContext("2d");
          context.scale(scale, scale);
          context.drawImage(image, 0, 0);
          URL.revokeObjectURL(url);
          canvas.toBlob(function (blob) {
            if (blob) resolve(blob);
            else reject(new Error("the drawing is too large for a PNG; save it as SVG"));
          }, "image/png");
        };
        image.onerror = function () {
          URL.revokeObjectURL(url);
          reject(new Error("the drawing could not be rendered"));
        };
        image.src = url;
      });
    }

    // The root and the selected path, as the address names them.
    function exportName() {
      var parts = [shape.root.name];
      if (selectedPath) parts = parts.concat(selectedPath.split("/"));
      return parts.join("-");
    }

    function save(blob, name) {
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    // What went wrong stays on the button, where the reader just looked.
    function failed(button, error) {
      button.title = "Could not save: " + error.message;
      button.classList.add("cd-dg-failed");
    }

    var exportGroup = document.createElement("div");
    exportGroup.className = "cd-dg-joined cd-dg-export";
    exportGroup.setAttribute("role", "group");
    exportGroup.setAttribute("aria-label", "Save the drawing as an image");
    toolbar.appendChild(exportGroup);
    var pngButton = toolButton(exportGroup, "cd-dg-export-png", "PNG",
      "Save the drawing as a PNG image", function () {
        exportPng().then(function (blob) {
          pngButton.classList.remove("cd-dg-failed");
          save(blob, exportName() + ".png");
        }, function (error) { failed(pngButton, error); });
      });
    toolButton(exportGroup, "cd-dg-export-svg", "SVG",
      "Save the drawing as an SVG image", function () {
        save(new Blob([exportSvg()], { type: "image/svg+xml" }), exportName() + ".svg");
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
        // Left only climbs and leaves the branch open behind it, the way
        // XSDDiagram does: a reader stepping back usually means to come again.
        // Shift+Left closes — the box under the cursor if it is open, else
        // the branch the cursor stands in, taking the cursor to its head.
        case "ArrowLeft":
          if (!event.shiftKey) { moveTo(parentElement(box)); break; }
          if (item.expandable && open[item.key]) { toggle(item); break; }
          var head = parentElement(box);
          if (!head) break;
          moveTo(head);
          if (open[head.item.key]) toggle(head.item);
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
      view: function () { return { scale: view.scale, x: view.x, y: view.y }; },
      exportSvg: exportSvg,
      exportPng: exportPng,
      exportName: exportName
    };
  }

  window.CpacsDiagram = {
    structure: structure,
    layout: layout,
    mount: mount
  };
})();
