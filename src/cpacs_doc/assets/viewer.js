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
    shownType: null,   // type displayed in place of the selected node's detail
    shownSection: null, // documentation section displayed in its place
    tab: "tree"        // half of the left column the reader last chose
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

  // The same reading of the same words as the type pages give. Two copies of
  // the prose, as with the compositors above: the generator writes the pages in
  // Python and the viewer builds its panel here.
  var FACET_GLOSS = {
    minInclusive: "The value must be this or greater.",
    maxInclusive: "The value must be this or less.",
    minExclusive: "The value must be greater than this.",
    maxExclusive: "The value must be less than this.",
    pattern: "The value must match this regular expression.",
    length: "The value must be exactly this long.",
    minLength: "The value must be at least this long.",
    maxLength: "The value must be at most this long.",
    totalDigits: "The value must have at most this many digits in all.",
    fractionDigits: "The value must have at most this many digits after the point.",
    whiteSpace: "How whitespace is treated before the value is checked."
  };

  function facetTerm(facet) {
    var term = element("span", "cd-facet", facet.name);
    term.setAttribute("tabindex", "0");
    var tip = element("span", "cd-tip", FACET_GLOSS[facet.name] || "");
    tip.setAttribute("role", "note");
    term.appendChild(tip);
    return term;
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
    // The pane is the tab panel; the tree proper is inside it, so the rows
    // have something that owns them either way.
    var group = element("div", "cd-treeroot");
    group.setAttribute("role", "tree");
    group.setAttribute("aria-label", "Instance tree");
    group.appendChild(renderNode(root, [], 0, 1, 1));
    container.appendChild(group);
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
      hintUsed();

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

  /* ---- the keyboard hint ----
   *
   * The tree is the one control here whose keys cannot be read off it, and a
   * reader who never presses one never learns they exist. So it is said once,
   * quietly, and taken back the moment it is no longer news — the first key in
   * the tree, or the button. Remembered like the tree width; the reader who
   * has moved a cursor once does not need telling again.
   */
  var HINT_KEY = "cpacs-doc.keyboardHint";
  var hintIsAutomatic = false;
  var HINT_ITEMS = [
    [["\u2191", "\u2193"], "move"],
    [["\u2192", "\u2190"], "open, close"],
    [["Enter"], "details"],
    [["/"], "search"],
    // The way back. Enter without it strands a reader in the detail panel,
    // and the same key closes the search results and this hint.
    [["Esc"], "back to the tree"]
  ];

  function hintSeen() {
    try {
      return window.localStorage.getItem(HINT_KEY) === "seen";
    } catch (e) {
      return false;  // private mode: show it, do not fail
    }
  }

  function markHelp(open) {
    var help = document.getElementById("cd-help");
    if (!help) return;
    help.setAttribute("aria-expanded", String(open));
    if (open) help.setAttribute("aria-controls", "cd-hint");
    else help.removeAttribute("aria-controls");
  }

  function hideHint() {
    var hint = document.getElementById("cd-hint");
    if (!hint) return;
    hint.parentNode.removeChild(hint);
    hintIsAutomatic = false;
    markHelp(false);
    try { window.localStorage.setItem(HINT_KEY, "seen"); } catch (e) { /* private mode */ }
  }

  // Using the keys takes back the hint that appeared by itself: it has just
  // been proved superfluous. One the reader asked for stays until the reader
  // closes it — being shown the keys and then having them snatched away for
  // trying one is not help.
  function hintUsed() {
    if (hintIsAutomatic) hideHint();
  }

  function setupHelp() {
    var help = document.getElementById("cd-help");
    if (!help) return;
    help.addEventListener("click", function () {
      if (document.getElementById("cd-hint")) hideHint();
      else showHint(false);
    });
  }

  function setupHint() {
    if (!hintSeen()) showHint(true);
  }

  function showHint(automatic) {
    if (document.getElementById("cd-hint")) return;
    var tree = document.getElementById("cd-tree");
    if (!tree || !tree.parentNode) return;

    var hint = element("div", "cd-hint");
    hint.id = "cd-hint";
    hint.setAttribute("role", "note");
    hint.appendChild(element("span", "cd-hint-lead", "Keyboard"));

    for (var i = 0; i < HINT_ITEMS.length; i++) {
      var item = element("span", "cd-hint-item");
      var keys = HINT_ITEMS[i][0];
      for (var k = 0; k < keys.length; k++) {
        item.appendChild(element("kbd", null, keys[k]));
      }
      item.appendChild(element("span", "cd-hint-what", HINT_ITEMS[i][1]));
      hint.appendChild(item);
    }

    var close = element("button", "cd-hint-close", "\u00D7");
    close.setAttribute("aria-label", "Hide the keyboard hint");
    close.addEventListener("click", hideHint);
    hint.appendChild(close);

    // Ahead of the tree, so it is read before what it describes.
    tree.parentNode.insertBefore(hint, tree);
    hintIsAutomatic = automatic;
    markHelp(true);
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
        } else if (document.getElementById("cd-hint")) {
          hideHint();
        } else if (docsAreOpen()) {
          showPane("tree");
          focusCursor();
        } else {
          focusCursor();
        }
        event.preventDefault();
        return;
      }
      // Straight after a page load the focus is nowhere, and an arrow key
      // would scroll a page that does not scroll: both panes carry their own
      // scrollbar. The reader meant the tree. Only an event that reached the
      // document from the body itself qualifies — anything focused, the tree
      // included, has handled its own keys by now.
      if (event.target === document.body || event.target === document.documentElement) {
        if (event.key.indexOf("Arrow") === 0) {
          hintUsed();
          focusCursor();
          event.preventDefault();
        }
      }
    });
  }

  function setupListKeys(id) {
    var panel = document.getElementById(id);
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
    state.shownSection = null;
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

    if (state.shownSection) {
      renderSectionDetail(panel, state.shownSection);
      return;
    }

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
    // Nowhere else would a reader learn it: the predecessor never wrote a
    // declared default out, and the schema is what it exists to replace.
    var declared = declaredValue(decl);
    if (declared) meta.appendChild(element("span", null, " \u00B7 " + declared));
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
          { head: "Default", cell: valueCell },
          { head: "Description", cell: function (a) { return text(documentationText(a)); } },
          { head: "Inherited from", cell: function (a) {
              return text(a.inherited ? a.declaredIn : "", null, "cd-inherited"); } }
        ]);
        appendChildTable(panel, type.children);
        appendTable(panel, "Value constraints", type.facets, [
          { head: "Constraint", cell: facetTerm },
          { head: "Value", cell: function (f) { return text(f.value, "code"); } }
        ]);
        appendTable(panel, "Allowed values", type.enumeration, [
          { head: "Value", cell: function (v) { return text(v.value, "code"); } },
          { head: "Description", cell: function (v) { return text(documentationText(v)); } }
        ]);
      }
  }

  // A default is what an instance means by leaving the element out; a fixed
  // value is the only one it may write. The schema's own word says which.
  function declaredValue(entry) {
    if (entry.fixed !== undefined && entry.fixed !== null) return "fixed " + entry.fixed;
    if (entry["default"] !== undefined && entry["default"] !== null) {
      return "default " + entry["default"];
    }
    return "";
  }

  // The same value under a heading that already names it. Saying "default" in
  // a column headed Default says it twice; a fixed value still needs its mark,
  // because it is not a default.
  function valueCell(entry) {
    var cell = element("span");
    if (entry.fixed !== undefined && entry.fixed !== null) {
      cell.appendChild(element("code", null, entry.fixed));
      cell.appendChild(element("span", "cd-fixed", " fixed"));
    } else if (entry["default"] !== undefined && entry["default"] !== null) {
      cell.appendChild(element("code", null, entry["default"]));
    }
    return cell;
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
    var type = state.model.types[typeName];
    if (!type) {
      // Not in this schema: leave the name as text rather than link nowhere.
      return element("code", null, typeName);
    }
    // An anonymous type is labelled with its base: its synthetic name says
    // where it was declared, which the row it sits in has just said, while the
    // base says what may be written there. The values are one click away.
    var label = type.anonymous && type.base ? type.base : typeName;
    // Switching the panel rather than following a link keeps the tree, and its
    // selection, in place. Where a type is worth citing, the panel offers the
    // static page explicitly.
    var button = element("button", "cd-crumb");
    button.appendChild(element("code", null, label));
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
    var headings = ["Name", "Type", "Occurrence", "Default", "Description"];
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
        groupCell.setAttribute("colspan", "4");
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
      var valueTd = element("td");
      valueTd.appendChild(valueCell(member));
      row.appendChild(valueTd);
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

  function renderSectionDetail(panel, slug) {
    var section = sectionBySlug(slug);
    if (!section) {
      panel.appendChild(element("h1", null, "Not found"));
      panel.appendChild(element("p", "cd-kind", "No section at " + slug + "."));
      return;
    }

    var nav = element("nav", "cd-breadcrumb");
    var back = element("button", "cd-crumb", "\u2190 back to the tree");
    back.addEventListener("click", function () {
      state.shownSection = null;
      showPane("tree");
      select(state.path);
    });
    nav.appendChild(back);
    panel.appendChild(nav);

    panel.appendChild(element("h1", null, section.title));

    var meta = element("p", "cd-kind");
    var page = element("a", null, "citable page");
    page.href = state.root + "/doc/" + section.slug + "/index.html";
    meta.appendChild(page);
    panel.appendChild(meta);

    var body = element("div", "cd-remarks");
    // Rendered once, by the generator, as everything else here is.
    body.innerHTML = withRoot(section.html);
    panel.appendChild(body);
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
  /* ---- the general documentation ----
   *
   * The prose that belongs to the schema as a whole hangs off the root
   * element's type, where the viewer would only ever show it as one scroll
   * behind one node — 31 sections and 5,720 words in CPACS 3.5.1. Split by the
   * extractor, each section is an entry here, opens in the detail panel like a
   * type, and has a page of its own to cite.
   *
   * The list is the document's own table of contents, in document order and
   * with the titles as written. Grouping the twenty version entries under a
   * heading of our own would mean deciding from a title what a section is
   * about; when a title stops matching the guess, the grouping breaks quietly.
   * If they belong together, the schema can say so by nesting them.
   */

  function sections() {
    return (state.model.documentation && state.model.documentation.sections) || [];
  }

  function sectionBySlug(slug) {
    var list = sections();
    for (var i = 0; i < list.length; i++) {
      if (list[i].slug === slug) return list[i];
    }
    return null;
  }

  function renderDocs() {
    var pane = document.getElementById("cd-docs");
    pane.textContent = "";
    var list = sections();
    var box = element("div", "cd-result-list");
    for (var i = 0; i < list.length; i++) {
      box.appendChild(docEntry(list[i]));
    }
    pane.appendChild(box);
  }

  function docEntry(section) {
    var row = element("button", "cd-result");
    if (section.slug === state.shownSection) row.className += " cd-selected";
    row.appendChild(element("span", "cd-result-label", section.title));
    row.addEventListener("click", function () { showSection(section.slug); });
    return row;
  }

  function showSection(slug) {
    state.shownType = null;
    state.shownSection = slug;
    renderDocs();
    renderDetail();
    var panel = document.getElementById("cd-detail");
    if (panel && panel.scrollTo) panel.scrollTo(0, 0);
  }

  function setupDocs() {
    var tabs = document.getElementById("cd-tabs");
    if (!tabs) return;
    // No sections, no tabs: one half is not a choice, and a strip naming only
    // what is already on screen says nothing.
    if (!sections().length) return;
    tabs.hidden = false;

    // Only now are the panes halves of something; until the tabs exist there
    // is nothing for a tab panel to belong to.
    label("cd-tree", "cd-tab-tree");
    label("cd-docs", "cd-tab-docs");

    tabs.addEventListener("click", function (event) {
      var tab = event.target;
      if (tab.id === "cd-tab-docs") { renderDocs(); showPane("docs"); }
      else if (tab.id === "cd-tab-tree") { showPane("tree"); focusCursor(); }
    });

    // A tab strip is one tab stop; the arrow keys move within it.
    tabs.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      var other = document.getElementById(
        document.activeElement.id === "cd-tab-docs" ? "cd-tab-tree" : "cd-tab-docs"
      );
      if (!other) return;
      other.focus();
      other.click();
      event.preventDefault();
    });
  }

  function label(paneId, tabId) {
    var pane = document.getElementById(paneId);
    if (!pane) return;
    pane.setAttribute("role", "tabpanel");
    pane.setAttribute("aria-labelledby", tabId);
  }

  function closeSearch(returnFocus) {
    var field = document.getElementById("cd-search");
    if (field) field.value = "";
    // Back to whichever half the reader was in, not always the tree.
    showPane(state.tab);
    document.getElementById("cd-search-count").textContent = "";
    if (returnFocus && state.tab === "tree") focusCursor();
  }

  // One slot, three occupants: the tree, the search results, and the
   // documentation. A second navigation area for eleven chapters would cost
   // more room than the chapters are worth, and the reader is never reading
   // two of the three at once.
  function showPane(name) {
    document.getElementById("cd-tree").hidden = name !== "tree";
    document.getElementById("cd-results").hidden = name !== "results";
    document.getElementById("cd-docs").hidden = name !== "docs";
    if (name !== "results") state.tab = name;
    // Search results are the third occupant of the slot and have no tab of
    // their own: while they are up, neither half is the current one.
    markTab("cd-tab-tree", name === "tree");
    markTab("cd-tab-docs", name === "docs");
  }

  function markTab(id, current) {
    var tab = document.getElementById(id);
    if (!tab) return;
    tab.setAttribute("aria-selected", String(current));
    tab.tabIndex = current ? 0 : -1;
  }

  function docsAreOpen() {
    var pane = document.getElementById("cd-docs");
    return !!pane && !pane.hidden;
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
          showPane("tree");
          document.getElementById("cd-search-count").textContent = "";
          return;
        }
        renderResults(hits, field.value.trim());
        showPane("results");
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
    setupListKeys("cd-results");
    setupListKeys("cd-docs");
    setupGlobalKeys();
    setupHelp();

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
        setupDocs();
        setupHint();
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