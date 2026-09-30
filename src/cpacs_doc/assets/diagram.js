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

  window.CpacsDiagram = {
    structure: structure
  };
})();
