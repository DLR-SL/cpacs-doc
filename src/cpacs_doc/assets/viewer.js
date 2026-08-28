/*
 * The viewer: resolves a tree path, renders the tree, shows the detail panel.
 *
 * Served as 404.html from arbitrary path depth, so nothing here may use a
 * relative URL: the browser would resolve it against the requested path rather
 * than against this file. The output root is derived from the requested path
 * instead — everything before the first "/tree/" segment. "tree" occurs nowhere
 * as an element name in the instance tree, so the split is unambiguous.
 *
 * Only expanded nodes are put into the DOM. The full tree has 54,552 nodes;
 * rendering it in one go is not a performance concern to be optimised later,
 * it is the reason the renderer is written the way it is.
 */

(function () {
  "use strict";

  var TREE_SEGMENT = "/tree/";
  var MODEL_FILE = "/cpacs-doc-model.json";
  var ROOT_TOKEN = "%ROOT%";

  var state = {
    root: "",          // path prefix the site is deployed under
    model: null,
    path: [],          // selected instance path, without the root element
    cursor: [],        // path the keyboard points at, apart from the selection
    cursorIndex: null, // position of the cursor row in `rows`
    rows: [],          // rendered rows in visual order, rebuilt with the tree
    expanded: null,    // Set of expanded paths
    nodeByPath: null,  // path -> model node
    searchEntries: null,  // built on first search, not on load
    shownType: null    // type displayed in place of the selected node's detail
  };

  function parseLocation() {
    var pathname = decodeURIComponent(window.location.pathname);
    var index = pathname.indexOf(TREE_SEGMENT);
    if (index === -1) {
      return null;
    }
    var rest = pathname.slice(index + TREE_SEGMENT.length);
    return {
      root: pathname.slice(0, index),
      segments: rest.split("/").filter(function (s) { return s.length > 0; })
    };
  }

  function declaration(node) {
    return state.model.declarations[node.d] || {};
  }

  function childrenOf(node) {
    return node.children || [];
  }

  function indexTree() {
    // Paths are built once so selection and expansion are lookups rather than
    // repeated walks. Only the path string is stored, not a copy of the node.
    state.nodeByPath = new Map();
    var root = state.model.tree;
    if (!root) return;
    var stack = [[root, []]];
    while (stack.length) {
      var item = stack.pop();
      var node = item[0];
      var path = item[1];
      // Where two elements share a path — 860 of them do, through the
      // branches of a choice — the first one found wins.
      var key = path.join("/");
      if (!state.nodeByPath.has(key)) {
        state.nodeByPath.set(key, node);
      }
      var children = childrenOf(node);
      for (var i = children.length - 1; i >= 0; i--) {
        // A group has no instance path: its members sit at the parent's level.
        stack.push([children[i], path.concat(declaration(children[i]).name || "?")]);
      }
    }
  }

  function expandAncestors(segments) {
    state.expanded = state.expanded || new Set();
    state.expanded.add("");
    for (var i = 1; i <= segments.length; i++) {
      state.expanded.add(segments.slice(0, i).join("/"));
    }
  }

  // "sequence" and "all" are schema words for a distinction that matters to
  // anyone writing an instance: whether the children have to appear in the
  // given order. Spelling it out is worth more than the vocabulary term.
  // The schema word carries the row; the explanation appears on hover and
  // focus, so the table stays quiet for readers who know the vocabulary.
  var COMPOSITOR_GLOSS = {
    sequence: "The children below must appear in exactly this order. "
      + "Each may repeat as often as its own occurrence allows.",
    all: "The children below may appear in any order. Each may appear at most once.",
    choice: "Exactly one of the alternatives below may appear, "
      + "unless the occurrence next to this line says otherwise."
  };

  function compositorGloss(name) {
    return COMPOSITOR_GLOSS[name] || "";
  }

  function cardinality(decl) {
    var min = decl.minOccurs === undefined ? 1 : decl.minOccurs;
    var max = decl.maxOccurs === undefined ? 1 : decl.maxOccurs;
    var upper = max === null ? "\u221E" : String(max);
    return String(min) === upper ? String(min) : min + "\u2026" + upper;
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderTree() {
    var container = document.getElementById("cd-tree");
    // Read before the rebuild: the row holding focus is about to be destroyed,
    // and the cursor may only take the focus back if the reader was in the
    // tree to begin with — a click or the initial load must not steal it.
    var hadFocus = container.contains(document.activeElement);
    container.textContent = "";
    state.rows = [];
    state.cursorIndex = null;
    var root = state.model.tree;
    if (!root) {
      container.appendChild(element("p", "cd-empty", "The model contains no tree."));
      return;
    }
    container.appendChild(renderNode(root, [], 0, 1, 1));
    restoreCursor(hadFocus);
  }

  function renderNode(node, path, depth, position, total) {
    var decl = declaration(node);
    var key = path.join("/");
    var children = childrenOf(node);
    var isExpanded = state.expanded.has(key);
    var isSelected = key === state.path.join("/");

    var min = decl.minOccurs === undefined ? 1 : decl.minOccurs;
    var max = decl.maxOccurs === undefined ? 1 : decl.maxOccurs;
    var classes = ["cd-node", min === 0 ? "cd-optional" : "cd-required"];
    if (max === null || max > 1) classes.push("cd-repeatable");
    if (isSelected) classes.push("cd-selected");

    var item = element("div", classes.join(" "));
    item.style.paddingLeft = depth * 16 + "px";
    // The tree is flat in the DOM as it is on screen (decision 0008): every row
    // states its own place in the hierarchy instead of being wrapped in nested
    // groups. The row itself is the treeitem, and the cursor row is the only
    // tab stop, so entering the tree costs one Tab and not two per row.
    item.setAttribute("role", "treeitem");
    item.setAttribute("aria-level", String(depth + 1));
    item.setAttribute("aria-posinset", String(position));
    item.setAttribute("aria-setsize", String(total));
    item.setAttribute("aria-selected", String(isSelected));
    if (children.length) item.setAttribute("aria-expanded", String(isExpanded));
    item.tabIndex = -1;

    var toggle = element("button", "cd-toggle", children.length ? (isExpanded ? "\u2212" : "+") : "\u00B7");
    toggle.disabled = children.length === 0;
    // The row carries aria-expanded now, and the toggle repeats nothing: it
    // stays reachable with the pointer and out of the keyboard's way.
    toggle.tabIndex = -1;
    toggle.setAttribute("aria-hidden", "true");
    toggle.addEventListener("click", function (event) {
      event.stopPropagation();
      if (isExpanded) state.expanded.delete(key); else state.expanded.add(key);
      state.cursor = path;
      renderTree();
    });
    item.appendChild(toggle);

    var label = element("button", "cd-label");
    label.tabIndex = -1;
    label.appendChild(element("span", "cd-name", decl.name || "?"));
    if (depth > 0) {
      label.appendChild(element("span", "cd-cardinality", cardinality(decl)));
    }
    if (decl.alternative) {
      // The tree stays flat; the constraint rides on the node it applies to.
      var mark = element("span", "cd-alternative", "\u2442");
      // Reached through the row rather than as a tab stop of its own: the
      // explanation appears when the row takes focus, see the stylesheet.
      mark.setAttribute("tabindex", "-1");
      var tip = element("span", "cd-tip",
        "One of several alternatives: only one branch of a choice may appear. "
        + "The type page lists the combinations.");
      tip.setAttribute("role", "note");
      mark.appendChild(tip);
      label.appendChild(mark);
    }
    // The type name is not repeated here: for most nodes it merely echoes the
    // element name, and the detail panel states it precisely.
    label.addEventListener("click", function () { select(path); });
    item.appendChild(label);

    state.rows.push({
      key: key,
      path: path,
      depth: depth,
      element: item,
      hasChildren: children.length > 0,
      expanded: isExpanded
    });

    var wrapper = element("div", "cd-subtree");
    // The wrapper only holds a row together with its subtree and means nothing
    // of its own, so it is skipped when the tree's items are computed.
    wrapper.setAttribute("role", "none");
    wrapper.appendChild(item);

    if (isExpanded) {
      for (var i = 0; i < children.length; i++) {
        var childName = declaration(children[i]).name || "?";
        wrapper.appendChild(renderNode(
          children[i], path.concat(childName), depth + 1, i + 1, children.length
        ));
      }
    }
    return wrapper;
  }

  /* ---- keyboard (F1, N13) ----
   *
   * The cursor is where the keyboard points; the selection is what the detail
   * panel shows and what the URL names. The two are usually the same row and
   * need not be: arrow keys move the cursor alone, Space and Enter commit it.
   * Were every arrow key to select, each keystroke would push a history entry
   * and the browser's back button would be useless after a few rows.
   *
   * Movement itself does not re-render. `renderTree()` rebuilds the container
   * from scratch, which is right for expanding and collapsing and far too much
   * for a step from one row to the next: that is two attribute changes.
   */

  function moveCursor(index, focusRow) {
    if (!state.rows.length) return;
    index = Math.max(0, Math.min(index, state.rows.length - 1));
    var previous = state.rows[state.cursorIndex];
    if (previous) {
      previous.element.classList.remove("cd-cursor");
      previous.element.tabIndex = -1;
    }
    var row = state.rows[index];
    state.cursorIndex = index;
    state.cursor = row.path;
    row.element.classList.add("cd-cursor");
    row.element.tabIndex = 0;
    if (focusRow === false) return;
    row.element.focus();
    if (row.element.scrollIntoView) row.element.scrollIntoView({ block: "nearest" });
  }

  function indexForPath(path) {
    // Where two rows share a path — 860 do, through the branches of a choice —
    // the first one wins, as it does in `indexTree()`. A cursor whose row is
    // gone, because an ancestor was collapsed, falls back to that ancestor.
    var segments = (path || []).slice();
    for (;;) {
      var key = segments.join("/");
      for (var i = 0; i < state.rows.length; i++) {
        if (state.rows[i].key === key) return i;
      }
      if (!segments.length) return 0;
      segments.pop();
    }
  }

  function restoreCursor(focusRow) {
    if (!state.rows.length) return;
    moveCursor(indexForPath(state.cursor), focusRow);
  }

  function focusCursor() {
    var row = state.rows[state.cursorIndex];
    if (!row) return;
    row.element.focus();
    if (row.element.scrollIntoView) row.element.scrollIntoView({ block: "nearest" });
  }

  function focusDetail() {
    var panel = document.getElementById("cd-detail");
    if (!panel) return;
    panel.focus();
    if (panel.scrollTo) panel.scrollTo(0, 0);
  }

  function parentIndex(index) {
    var depth = state.rows[index].depth;
    for (var i = index - 1; i >= 0; i--) {
      if (state.rows[i].depth < depth) return i;
    }
    return index;
  }

  function setupTreeKeys() {
    var container = document.getElementById("cd-tree");
    if (!container) return;
    // One listener on the container, not one per row: the rows are rebuilt on
    // every expansion, and there are up to 54,552 of them.
    container.addEventListener("keydown", function (event) {
      // Alt+Left is the browser's back and Ctrl+Home the document start: the
      // tree does not take keys that carry a modifier.
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      var index = state.cursorIndex;
      var row = state.rows[index];
      if (!row) return;

      if (event.key === "ArrowDown") {
        moveCursor(index + 1);
      } else if (event.key === "ArrowUp") {
        moveCursor(index - 1);
      } else if (event.key === "Home") {
        moveCursor(0);
      } else if (event.key === "End") {
        moveCursor(state.rows.length - 1);
      } else if (event.key === "ArrowRight") {
        // Open what is closed, then step inward: the first child is the next
        // row, because the rows are held in the order they are drawn.
        if (row.hasChildren && !row.expanded) {
          state.expanded.add(row.key);
          renderTree();
        } else if (row.hasChildren) {
          moveCursor(index + 1);
        }
      } else if (event.key === "ArrowLeft") {
        if (row.expanded) {
          state.expanded.delete(row.key);
          renderTree();
        } else {
          moveCursor(parentIndex(index));
        }
      } else if (event.key === " " || event.key === "Spacebar") {
        select(row.path);
      } else if (event.key === "Enter") {
        select(row.path);
        focusDetail();
      } else {
        return;
      }
      event.preventDefault();
    });
  }

  function isTextField(node) {
    if (!node) return false;
    return node.tagName === "INPUT" || node.tagName === "TEXTAREA"
      || node.isContentEditable === true;
  }

  function setupGlobalKeys() {
    document.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (isTextField(event.target)) return;
      if (event.key === "/") {
        var field = document.getElementById("cd-search");
        if (!field) return;
        field.focus();
        field.select();
        event.preventDefault();
        return;
      }
      if (event.key === "Escape") {
        if (!document.getElementById("cd-results").hidden) {
          closeSearch(true);
        } else {
          focusCursor();
        }
        event.preventDefault();
      }
    });
  }

  function setupResultKeys() {
    var panel = document.getElementById("cd-results");
    if (!panel) return;
    panel.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      var current = document.activeElement;
      if (!current || current.className.indexOf("cd-result") !== 0) return;
      var next = null;
      if (event.key === "ArrowDown") next = current.nextSibling;
      else if (event.key === "ArrowUp") next = current.previousSibling;
      else return;
      if (next && next.focus) next.focus();
      event.preventDefault();
    });
  }

  function select(path) {
    state.shownType = null;
    state.path = path;
    state.cursor = path;
    expandAncestors(path);
    // The root element is part of the URL: it is part of an instance path, and
    // the "show in tree" links on type pages are written that way.
    var segments = [declaration(state.model.tree).name].concat(path);
    var url = state.root + TREE_SEGMENT + segments.join("/") + "/";
    window.history.pushState({ path: path }, "", url);
    renderTree();
    renderDetail();
  }

  function withRoot(html) {
    // The empty string is a valid root — a site deployed at "/" — and yields
    // an absolute "/media/…". A relative fallback would resolve against the
    // requested tree path instead, which this file must never do.
    return html.split(ROOT_TOKEN).join(state.root);
  }

  function typeHref(typeName) {
    return state.root + "/type/" + typeName.split("/").join("--") + "/index.html";
  }

  function renderDetail() {
    var panel = document.getElementById("cd-detail");
    panel.textContent = "";

    if (state.shownType) {
      renderTypeDetail(panel, state.shownType);
      return;
    }

    var key = state.path.join("/");
    var node = state.nodeByPath.get(key);
    if (!node) {
      panel.appendChild(element("h1", null, "Not found"));
      panel.appendChild(element(
        "p", "cd-kind",
        "No element at " + (key ? "cpacs/" + key : "the requested path") + " in this schema."
      ));
      return;
    }

    var decl = declaration(node);
    panel.appendChild(renderBreadcrumb());
    panel.appendChild(element("h1", null, decl.name || "?"));

    var meta = element("p", "cd-kind");
    meta.appendChild(element("span", null, "occurs " + cardinality(decl)));
    panel.appendChild(meta);

    if (decl.documentation && decl.documentation.text) {
      panel.appendChild(element("p", "cd-elementdoc", decl.documentation.text));
    }

    if (decl.type) {
      var line = element("p", "cd-kind");
      line.appendChild(document.createTextNode("Type: "));
      line.appendChild(typeCell(decl.type));
      panel.appendChild(line);

      appendTypeBody(panel, state.model.types[decl.type]);
    }
  }

  function appendTypeBody(panel, type) {
      if (type) {
        if (type.documentation) {
          // The fragments were rendered once, by the generator. Inserting them
          // here keeps one implementation of the ddue vocabulary.
          if (type.documentation.summaryHtml) {
            var summary = element("div", "cd-summary");
            summary.innerHTML = withRoot(type.documentation.summaryHtml);
            panel.appendChild(summary);
          }
          if (type.documentation.remarksHtml) {
            var remarks = element("div", "cd-remarks");
            remarks.innerHTML = withRoot(type.documentation.remarksHtml);
            panel.appendChild(remarks);
          }
        }
        // The detail panel carries the same tables as the static type page.
        // Attributes appear nowhere else in the viewer, and repeating the
        // children costs little next to having to read them off the tree.
        appendTable(panel, "Attributes", type.attributes, [
          { head: "Name", cell: function (a) { return text("@" + a.name, "code"); } },
          { head: "Type", cell: function (a) { return typeCell(a.type); } },
          { head: "Use", cell: function (a) { return text(a.use || ""); } },
          { head: "Default", cell: function (a) { return text(a["default"] || a.fixed || ""); } },
          { head: "Description", cell: function (a) { return text(documentationText(a)); } },
          { head: "Inherited from", cell: function (a) {
              return text(a.inherited ? a.declaredIn : "", null, "cd-inherited"); } }
        ]);
        appendChildTable(panel, type.children);
        appendTable(panel, "Allowed values", type.enumeration, [
          { head: "Value", cell: function (v) { return text(v.value, "code"); } },
          { head: "Description", cell: function (v) { return text(documentationText(v)); } }
        ]);
      }
  }

  function documentationText(entry) {
    return (entry.documentation && entry.documentation.text) || "";
  }

  function text(value, tag, className) {
    return element(tag || "span", className || null, value);
  }

  function typeCell(typeName) {
    if (!typeName || typeName.indexOf("xsd:") === 0) {
      return element("code", null, typeName || "");
    }
    if (!state.model.types[typeName]) {
      // Not in this schema: leave the name as text rather than link nowhere.
      return element("code", null, typeName);
    }
    // Switching the panel rather than following a link keeps the tree, and its
    // selection, in place. Where a type is worth citing, the panel offers the
    // static page explicitly.
    var button = element("button", "cd-crumb");
    button.appendChild(element("code", null, typeName));
    button.addEventListener("click", function () { showType(typeName); });
    return button;
  }

  function showType(typeName) {
    state.shownType = typeName;
    renderDetail();
    var panel = document.getElementById("cd-detail");
    if (panel && panel.scrollTo) panel.scrollTo(0, 0);
  }

  function childCell(child) {
    // A child leads back into the tree; a type leads out to its page.
    var button = element("button", "cd-crumb");
    button.appendChild(element("code", null, child.name));
    button.addEventListener("click", function () { select(state.path.concat(child.name)); });
    return button;
  }

  function appendChildTable(panel, members) {
    if (!members || !members.length) return;
    panel.appendChild(element("h2", null, "Child elements"));
    var table = element("table");
    var head = element("tr");
    var headings = ["Name", "Type", "Occurrence", "Description"];
    for (var h = 0; h < headings.length; h++) head.appendChild(element("th", null, headings[h]));
    table.appendChild(head);
    appendChildRows(table, members, 0);
    panel.appendChild(table);
  }

  // A compositor governs a set of children, not each child on its own, so it
  // heads them as a row of its own instead of repeating in a column.
  function appendChildRows(table, members, depth) {
    for (var i = 0; i < members.length; i++) {
      var member = members[i];
      if (member.kind === "group") {
        var groupRow = element("tr", "cd-group cd-group-" + (member.compositor || ""));
        var groupCell = element("td");
        groupCell.setAttribute("colspan", "3");
        indent(groupCell, depth);
        var label = element("span", "cd-group-label");
        var mark = element("span", "cd-group-mark");
        mark.setAttribute("aria-hidden", "true");
        label.appendChild(mark);

        var term = element("span", "cd-group-term", member.compositor || "");
        // Focusable so the explanation is reachable without a pointer.
        term.setAttribute("tabindex", "0");
        var tip = element("span", "cd-tip", compositorGloss(member.compositor));
        tip.setAttribute("role", "note");
        term.appendChild(tip);
        label.appendChild(term);

        var occurrence = cardinality(member);
        if (occurrence !== "1") {
          label.appendChild(element("span", "cd-group-occurs", "\u00B7 " + occurrence));
        }
        groupCell.appendChild(label);
        groupRow.appendChild(groupCell);
        groupRow.appendChild(element("td"));
        table.appendChild(groupRow);
        appendChildRows(table, member.members || [], depth + 1);
        continue;
      }
      var row = element("tr");
      var nameCell = element("td");
      indent(nameCell, depth);
      nameCell.appendChild(childCell(member));
      row.appendChild(nameCell);
      var typeCellNode = element("td");
      typeCellNode.appendChild(typeCell(member.type));
      row.appendChild(typeCellNode);
      row.appendChild(text(cardinality(member), "td"));
      row.appendChild(text(documentationText(member), "td"));
      table.appendChild(row);
    }
  }

  function indent(cell, depth) {
    if (!depth) return;
    cell.className = "cd-indent";
    cell.style.setProperty("--depth", String(depth));
  }

  function appendTable(panel, heading, rows, columns) {
    if (!rows || !rows.length) return;
    panel.appendChild(element("h2", null, heading));
    var table = element("table");
    var head = element("tr");
    for (var c = 0; c < columns.length; c++) {
      head.appendChild(element("th", null, columns[c].head));
    }
    table.appendChild(head);
    for (var r = 0; r < rows.length; r++) {
      var row = element("tr");
      for (var i = 0; i < columns.length; i++) {
        var cell = element("td");
        cell.appendChild(columns[i].cell(rows[r]));
        row.appendChild(cell);
      }
      table.appendChild(row);
    }
    panel.appendChild(table);
  }

  function renderTypeDetail(panel, typeName) {
    var type = state.model.types[typeName] || {};

    var nav = element("nav", "cd-breadcrumb");
    var back = element("button", "cd-crumb", "\u2190 back to " + (state.path.length
      ? state.path[state.path.length - 1]
      : declaration(state.model.tree).name));
    // Always back to the selected node, never through the chain of type jumps:
    // the tree node is where the reader was, the types are a detour.
    back.addEventListener("click", function () { select(state.path); });
    nav.appendChild(back);
    panel.appendChild(nav);

    panel.appendChild(element("h1", null, typeName));

    var meta = element("p", "cd-kind");
    meta.appendChild(element("span", null, type.kind || "type"));
    if (type.base) {
      meta.appendChild(document.createTextNode(" \u00B7 " + (type.derivation || "derives from") + " "));
      meta.appendChild(typeCell(type.base));
    }
    if (type.compositor) {
      meta.appendChild(document.createTextNode(" \u00B7 " + type.compositor));
    }
    meta.appendChild(document.createTextNode(" \u00B7 "));
    var page = element("a", null, "citable page");
    page.href = typeHref(typeName);
    meta.appendChild(page);
    panel.appendChild(meta);

    appendTypeBody(panel, type);
  }

  function renderBreadcrumb() {
    var nav = element("nav", "cd-breadcrumb");
    var rootLink = element("button", "cd-crumb", "cpacs");
    rootLink.addEventListener("click", function () { select([]); });
    nav.appendChild(rootLink);
    var walked = [];
    for (var i = 0; i < state.path.length; i++) {
      walked = walked.concat(state.path[i]);
      nav.appendChild(document.createTextNode(" / "));
      var target = walked.slice();
      var crumb = element("button", "cd-crumb", state.path[i]);
      crumb.addEventListener("click", (function (path) {
        return function () { select(path); };
      })(target));
      nav.appendChild(crumb);
    }
    return nav;
  }

  var TREE_WIDTH_KEY = "cpacs-doc.treeWidth";
  var MIN_TREE_WIDTH = 200;

  function setupSplitter() {
    var splitter = document.getElementById("cd-splitter");
    var app = document.getElementById("cd-app");
    if (!splitter || !app) return;

    var stored = null;
    try { stored = window.localStorage.getItem(TREE_WIDTH_KEY); } catch (e) { stored = null; }
    if (stored) app.style.setProperty("--tree-width", stored + "px");

    function apply(px) {
      var limit = Math.max(MIN_TREE_WIDTH, Math.min(px, window.innerWidth - MIN_TREE_WIDTH));
      app.style.setProperty("--tree-width", limit + "px");
      try { window.localStorage.setItem(TREE_WIDTH_KEY, String(limit)); } catch (e) { /* private mode */ }
    }

    splitter.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      splitter.setPointerCapture(event.pointerId);
      var origin = app.getBoundingClientRect().left;
      function move(e) { apply(e.clientX - origin); }
      function stop() {
        splitter.removeEventListener("pointermove", move);
        splitter.removeEventListener("pointerup", stop);
      }
      splitter.addEventListener("pointermove", move);
      splitter.addEventListener("pointerup", stop);
    });

    // Keyboard equivalent, so the splitter is not a mouse-only control.
    splitter.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 64 : 16;
      var current = document.getElementById("cd-tree").getBoundingClientRect().width;
      if (event.key === "ArrowLeft") { apply(current - step); event.preventDefault(); }
      if (event.key === "ArrowRight") { apply(current + step); event.preventDefault(); }
    });
  }

  /* ---- search (F12–F14) ----
   *
   * Built from the model that is already loaded, so there is no separate index
   * to ship or keep in step. Ranking follows F13: an exact name first, then a
   * name that starts with the query, then any name containing it, then a path
   * segment, then body text — because someone typing `wingUID` wants the
   * element, not the twelve descriptions that mention it.
   */
  var SEARCH_LIMIT = 60;
  var SEARCH_DELAY = 120;

  var RANK = {
    exactName: 0,
    prefixName: 1,
    name: 2,
    attribute: 3,
    path: 4,
    text: 5
  };

  function buildSearchEntries() {
    var entries = [];
    state.nodeByPath.forEach(function (node, path) {
      var decl = declaration(node);
      entries.push({
        kind: "element",
        label: decl.name || "?",
        path: path,
        detail: path,
        type: decl.type || "",
        text: (decl.documentation && decl.documentation.text) || ""
      });
    });
    Object.keys(state.model.types).forEach(function (name) {
      var type = state.model.types[name];
      var documentation = type.documentation || {};
      entries.push({
        kind: "type",
        label: name,
        typeName: name,
        detail: type.kind || "type",
        text: documentation.summary || ""
      });
      (type.attributes || []).forEach(function (attribute) {
        entries.push({
          kind: "attribute",
          label: "@" + attribute.name,
          typeName: name,
          detail: name,
          text: (attribute.documentation && attribute.documentation.text) || ""
        });
      });
    });
    return entries;
  }

  function scoreEntry(entry, query) {
    var label = entry.label.toLowerCase();
    if (label === query) return RANK.exactName;
    if (label.indexOf(query) === 0) return RANK.prefixName;
    if (label.indexOf(query) !== -1) {
      return entry.kind === "attribute" ? RANK.attribute : RANK.name;
    }
    if (entry.path && entry.path.toLowerCase().indexOf(query) !== -1) return RANK.path;
    if (entry.text && entry.text.toLowerCase().indexOf(query) !== -1) return RANK.text;
    return -1;
  }

  function search(query) {
    query = query.trim().toLowerCase();
    if (query.length < 2) return null;
    if (!state.searchEntries) state.searchEntries = buildSearchEntries();

    // Collected into one bucket per rank rather than sorted as a whole: a
    // broad query matches tens of thousands of the 58,920 entries, and sorting
    // all of them to show sixty is where the time would go.
    var buckets = [[], [], [], [], [], []];
    var total = 0;
    for (var i = 0; i < state.searchEntries.length; i++) {
      var rank = scoreEntry(state.searchEntries[i], query);
      if (rank === -1) continue;
      buckets[rank].push(state.searchEntries[i]);
      total += 1;
    }

    var shown = [];
    for (var b = 0; b < buckets.length && shown.length < SEARCH_LIMIT; b++) {
      buckets[b].sort(function (x, y) {
        if (x.label.length !== y.label.length) return x.label.length - y.label.length;
        return x.label < y.label ? -1 : x.label > y.label ? 1 : 0;
      });
      shown = shown.concat(buckets[b].slice(0, SEARCH_LIMIT - shown.length));
    }
    return { shown: shown, total: total };
  }

  function renderResults(result, query) {
    var panel = document.getElementById("cd-results");
    var count = document.getElementById("cd-search-count");
    panel.textContent = "";

    if (!result.total) {
      count.textContent = "no matches";
      panel.appendChild(element("p", "cd-empty", "Nothing matches " + query + "."));
      return;
    }

    count.textContent = result.total > result.shown.length
      ? result.shown.length + " of " + result.total
      : String(result.total);

    var list = element("div", "cd-result-list");
    for (var i = 0; i < result.shown.length; i++) {
      list.appendChild(renderResult(result.shown[i]));
    }
    panel.appendChild(list);
  }

  function renderResult(entry) {
    var row = element("button", "cd-result");
    var label = element("span", "cd-result-label", entry.label);
    if (entry.kind === "type") label.className += " cd-result-type";
    row.appendChild(label);
    row.appendChild(element("span", "cd-result-detail", entry.detail));
    row.addEventListener("click", function () {
      if (entry.kind === "element") {
        // F14: results navigate into the tree, expanding the path. The stored
        // path already excludes the root element, as `state.path` does.
        closeSearch(false);
        select(entry.path ? entry.path.split("/") : []);
        focusCursor();
      } else {
        closeSearch(false);
        showType(entry.typeName);
        focusDetail();
      }
    });
    return row;
  }

  // The focus has to go somewhere once the results are gone. Whoever closes
  // the search says where: back to the tree cursor when the reader gave the
  // search up, nowhere when a result is opened and the target takes it.
  function closeSearch(returnFocus) {
    var field = document.getElementById("cd-search");
    if (field) field.value = "";
    showResults(false);
    document.getElementById("cd-search-count").textContent = "";
    if (returnFocus) focusCursor();
  }

  function showResults(on) {
    document.getElementById("cd-results").hidden = !on;
    document.getElementById("cd-tree").hidden = on;
  }

  function setupSearch() {
    var field = document.getElementById("cd-search");
    if (!field) return;
    var timer = null;

    field.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        var hits = search(field.value);
        if (hits === null) {
          showResults(false);
          document.getElementById("cd-search-count").textContent = "";
          return;
        }
        renderResults(hits, field.value.trim());
        showResults(true);
      }, SEARCH_DELAY);
    });

    field.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSearch(true);
      if (event.key === "ArrowDown") {
        var first = document.getElementById("cd-results").querySelector(".cd-result");
        if (first) {
          first.focus();
          event.preventDefault();
        }
      }
      if (event.key === "Enter") {
        var first = document.getElementById("cd-results").children[0];
        var button = first && first.children && first.children[0];
        if (button && button.click) button.click();
      }
    });
  }

  function fail(message) {
    document.getElementById("cd-app").textContent = "";
    var panel = element("div", "cd-error");
    panel.appendChild(element("h1", null, "Not found"));
    panel.appendChild(element("p", null, message));
    document.getElementById("cd-app").appendChild(panel);
  }

  function start() {
    var location = parseLocation();
    if (location === null) {
      // A genuine 404: a path that is not a tree path at all. Reporting it as
      // an error is the point (R3); routing everything into the viewer would
      // hide real broken links.
      fail("This address does not exist in the documentation.");
      return;
    }
    state.root = location.root;
    setupSplitter();
    setupSearch();
    setupTreeKeys();
    setupResultKeys();
    setupGlobalKeys();

    fetch(state.root + MODEL_FILE)
      .then(function (response) {
        if (!response.ok) throw new Error("model unavailable (" + response.status + ")");
        return response.json();
      })
      .then(function (model) {
        state.model = model;
        indexTree();
        var rootName = declaration(model.tree).name;
        var segments = location.segments;
        // The root element is part of the URL but not of the internal path.
        if (segments.length && segments[0] === rootName) segments = segments.slice(1);
        state.path = segments;
        state.cursor = segments;
        expandAncestors(segments);
        renderTree();
        renderDetail();
      })
      .catch(function (error) {
        fail("The documentation model could not be loaded: " + error.message);
      });
  }

  window.addEventListener("popstate", function () {
    var location = parseLocation();
    if (!location || !state.model) return;
    var segments = location.segments;
    var rootName = declaration(state.model.tree).name;
    if (segments.length && segments[0] === rootName) segments = segments.slice(1);
    state.path = segments;
    state.cursor = segments;
    expandAncestors(segments);
    renderTree();
    renderDetail();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();