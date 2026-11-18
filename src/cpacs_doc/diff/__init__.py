"""Compare two schemas and show the differences in the diagram.

`cpacs-doc diff OLD NEW -o DIR` builds the model of both schemas, compares them and writes

- ``diff.html``: one self-contained page, the diagram with the changes on it,
- ``report.md``: the full list, ``summary.md``: a short one for a pull request,
- ``diff.json``: everything.

The pieces: :mod:`typediff` compares the type catalogues, :mod:`treediff` merges the two
instance trees (renames, moves, attributes, compositor groups), :mod:`compat` classifies
each change, :mod:`typemap` finds renamed and merged types, :mod:`renames` reads the rename
decisions next to the new schema, :mod:`output` writes the files.
"""
