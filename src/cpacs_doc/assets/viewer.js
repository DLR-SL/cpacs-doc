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
    expanded: null,    // Set of expanded paths
    nodeByPath: null,  // path -> model node
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
      state.nodeByPath.set(path.join("/"), node);
      var children = childrenOf(node);
      for (var i = children.length - 1; i >= 0; i--) {
        var name = declaration(children[i]).name || "?";
        stack.push([children[i], path.concat(name)]);
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
  var COMPOSITOR_LABEL = {
    sequence: "in this order",
    all: "in any order",
    choice: "one of"
  };

  function compositorLabel(name) {
    return COMPOSITOR_LABEL[name] || name;
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
    container.textContent = "";
    var root = state.model.tree;
    if (!root) {
      container.appendChild(element("p", "cd-empty", "The model contains no tree."));
      return;
    }
    container.appendChild(renderNode(root, [], 0));
  }

  function renderNode(node, path, depth) {
    var key = path.join("/");
    var decl = declaration(node);
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

    var toggle = element("button", "cd-toggle", children.length ? (isExpanded ? "\u2212" : "+") : "\u00B7");
    toggle.disabled = children.length === 0;
    toggle.setAttribute("aria-expanded", String(isExpanded));
    toggle.addEventListener("click", function (event) {
      event.stopPropagation();
      if (isExpanded) state.expanded.delete(key); else state.expanded.add(key);
      renderTree();
    });
    item.appendChild(toggle);

    var label = element("button", "cd-label");
    label.appendChild(element("span", "cd-name", decl.name || "?"));
    if (depth > 0) {
      label.appendChild(element("span", "cd-cardinality", cardinality(decl)));
    }
    // The type name is not repeated here: for most nodes it merely echoes the
    // element name, and the detail panel states it precisely.
    label.addEventListener("click", function () { select(path); });
    item.appendChild(label);

    var wrapper = element("div", "cd-subtree");
    wrapper.appendChild(item);

    if (isExpanded) {
      for (var i = 0; i < children.length; i++) {
        var childName = declaration(children[i]).name || "?";
        wrapper.appendChild(renderNode(children[i], path.concat(childName), depth + 1));
      }
    }
    return wrapper;
  }

  function select(path) {
    state.shownType = null;
    state.path = path;
    expandAncestors(path);
    var url = state.root + TREE_SEGMENT + path.join("/") + (path.length ? "/" : "");
    window.history.pushState({ path: path }, "", url);
    renderTree();
    renderDetail();
  }

  function withRoot(html) {
    return html.split(ROOT_TOKEN).join(state.root || ".");
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
        var groupRow = element("tr", "cd-group");
        var groupCell = element("td");
        groupCell.setAttribute("colspan", "3");
        indent(groupCell, depth);
        groupCell.appendChild(element("span", "cd-group-label", groupLabel(member)));
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
    if (depth) cell.style.paddingLeft = (depth * 1.4).toFixed(1) + "rem";
  }

  function groupLabel(group) {
    var label = compositorLabel(group.compositor);
    var occurrence = cardinality(group);
    return occurrence === "1" ? label : label + " \u00B7 " + occurrence;
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
      meta.appendChild(document.createTextNode(" \u00B7 " + compositorLabel(type.compositor)));
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
