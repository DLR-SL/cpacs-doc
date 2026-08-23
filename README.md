# cpacs-doc

**Experimental.** A prototype documentation extractor for the CPACS schema, not
a supported deliverable and not a replacement for the current documentation
build. Interfaces and output format may change without notice.

Stage one of the three-stage architecture (extractor → generator → viewer). It
reads an XSD and produces two things:

* **the build report** — undocumented types, unknown `ddue` vocabulary,
  structural outliers, unresolvable figure references, ambiguous tree paths;
* **the intermediate model** — type catalogue, instance tree, media catalogue
  and report as one JSON document.

Nothing is rendered here. `ddue` markup is carried as plain text; turning it
into HTML belongs to the generator.

## Usage

```
cpacs-doc report schema/cpacs_schema.xsd
cpacs-doc build  schema/cpacs_schema.xsd -o build/
```

The media catalogue (`documentation/media.json`) is picked up automatically when
it sits next to the schema directory. `--media` points elsewhere, `--no-media`
skips it. Exit status is 1 when the report holds errors; `--tolerate-errors`
suppresses that.

## Installing

```
pip install -e ".[dev]"
pytest
```

Requires Python 3.10 and `lxml`. The extractor deliberately does not depend on
`cpacs-schema-tool` or on the viewer.

## Reporting rather than repairing

Where the schema deviates from its own conventions, the extractor reports and
moves on. It does not recover a documentation body from an unexpected wrapper,
does not infer a figure's file from its id, and does not translate vocabulary it
has not been told about. Silent repair would keep the underlying defect alive
and would oblige every later consumer to reimplement the same guess.

## Tools

`tools/survey_doc_vocabulary.py` counts the documentation vocabulary of a schema
and cross-checks the media catalogue against the file system. It has no
dependency on the package and can be run against any XSD.

`tools/convert_media_catalogue.py` migrates the figure catalogue out of the SHFB
project file into `media.json`, correcting file name capitalisation against the
file system on the way. A one-off migration, not part of the build.
