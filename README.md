# CPACS Documentation Generator

**Experimental.** A prototype documentation extractor for the CPACS schema, not
a supported deliverable and not a replacement for the current documentation
build. Interfaces and output format may change without notice.

It reads an XSD and produces a **build report** (undocumented types, unknown
`ddue` vocabulary, structural outliers, unresolvable figure references,
ambiguous tree paths) and an **intermediate model** (type catalogue, instance
tree, media catalogue and report as one JSON document). `serve` additionally
shows the model in a browser. Nothing is rendered to final HTML here.

Requires Python 3.10 or newer. The only runtime dependency is `lxml`, which
ships as a wheel on Windows, macOS and Linux — no compiler needed.

This project was written with AI assistance; the documentation it extracts was
not. See [section 5](#5-how-this-was-built).

---

## 1. Install

Pick **one** of the three paths below. If you have no preference, take uv: it is
what CI uses, and `uv.lock` pins the exact versions so every checkout resolves
identically.

### Path A — with uv (recommended)

**Install uv itself**, once per machine ([full
instructions](https://docs.astral.sh/uv/getting-started/installation/)):

```powershell
# Windows, PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal afterwards so the changed `PATH` takes effect, then check:

```
uv --version
```

**Set up the project**, from the repository root:

```
uv sync
```

That one command does everything: it downloads a suitable Python if none is
installed, creates the virtual environment in `.venv/`, installs `cpacs-doc` in
editable mode, and pulls the test tooling from the `dev` dependency group.

**Run things** by prefixing `uv run` — no `activate`, no manual `PATH` fiddling:

```
uv run pytest
uv run cpacs-doc report path/to/cpacs/schema/cpacs_schema.xsd
```

`uv run` re-syncs the environment first whenever it is out of date, so the
explicit `uv sync` above is really only a convenience for getting the download
over with.

> If you would rather type `cpacs-doc` without the prefix, activate the
> environment once per terminal: `.venv\Scripts\activate` on Windows,
> `source .venv/bin/activate` elsewhere.

### Path B — with pip and a virtual environment

Any Python 3.10 or newer will do. From the repository root:

```powershell
# Windows, PowerShell
python -m venv .venv
.venv\Scripts\activate
pip install -e . pytest
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -e . pytest
```

`pytest` has to be named explicitly: the test tooling sits in a PEP 735
`[dependency-groups]` block rather than in an extra, and a plain
`pip install -e .` does not pull it.

The environment has to be activated once per terminal; afterwards everything
runs without a prefix:

```
pytest
cpacs-doc report path/to/cpacs/schema/cpacs_schema.xsd
```

### Path C — with conda

If your workflow is conda-based, that works too. The package has no conda-only
dependencies, so let conda provide the interpreter and install the package with
pip *inside* the environment:

```
conda create -n cpacs-doc python=3.12
conda activate cpacs-doc
pip install -e . pytest
```

`pytest` again has to be named explicitly, for the same reason as in Path B.
Then run without any prefix:

```
pytest
cpacs-doc report path/to/cpacs/schema/cpacs_schema.xsd
```

### A note on Paths B and C

Neither is pinned — `uv.lock` does not apply there, so you get whatever versions
pip resolves at that moment. That is fine for using the tool, and it is the
reason CI installs with `uv sync --locked` instead.

---

## 2. Run

Three subcommands, all sharing one pipeline, so the report can never describe a
different run than the model does:

```
cpacs-doc report  path/to/cpacs/schema/cpacs_schema.xsd            # report only
cpacs-doc build   path/to/cpacs/schema/cpacs_schema.xsd -o build/  # report + model
cpacs-doc serve   path/to/cpacs/schema/cpacs_schema.xsd            # report + viewer
```

**How to type the commands in this README.** Everything below is written as the
bare command. Which form you actually type depends on the path you installed
with:

| Path | `cpacs-doc …` | `python …` |
| --- | --- | --- |
| A (uv) | `uv run cpacs-doc …` | `uv run python …` |
| B (venv) / C (conda) | `cpacs-doc …` | `python …`, environment activated |

On Path A nothing has to be activated; on Paths B and C the environment has to
be activated once per terminal, and then the bare command is the whole story.

### What `report` prints

A statistics line, then the findings grouped by code, then a verdict. Against
the real CPACS schema it looks like this:

```
types: 1206 (1121 documented) | tree: 54552 nodes (2848 in a choice), 53692 distinct paths, depth 22 | media: 98 entries

WARNING  TREE_PATH_AMBIGUOUS  (860)
    cpacs/vehicles/…/coefficientsBreakdown/otherComponents: reachable 2 times (differing cardinality ['(0, 1)', '(1, 1)'])  [cpacs_schema.xsd]
    … 858 more

INFO  MEDIA_ENTRY_UNREFERENCED  (14)
    catalogue defines 'bodyFixCoordSys', which no documentation references  [documentation/media.json]
    … 12 more

0 errors, 58 warnings, 817 notes
```

Only ten findings per code are shown; `--limit 0` shows all, `--limit N` shows
N. **Exit status is 1 when the report holds errors** (warnings and notes do not
fail the run), which is what makes it usable in CI. `--tolerate-errors` forces
exit 0 for exploratory runs.

### Where the figures come from

`documentation/media.json` is picked up automatically when it sits next to the
schema *directory*, i.e. this layout:

```
cpacs/
├── schema/
│   └── cpacs_schema.xsd     ← the argument you pass
└── documentation/
    ├── media.json           ← found automatically
    ├── figures/
    └── equations/
```

Anywhere else, point at it with `--media path/to/media.json`. `--no-media` skips
it entirely — without it you get a `MEDIA_CATALOGUE_NOT_GIVEN` warning as soon
as any documentation references a figure.

### `build`

Writes `build/cpacs-doc-model.json` and prints its size. `--site` additionally
generates the static type pages, `--media-root` overrides the directory the
catalogue's file paths resolve against (default: the catalogue's own directory).

`--single` writes `build/cpacs-doc.html` instead: the viewer, the model and the
figures in one document, which opens from a disk with no server behind it — 20.6
MB for CPACS 3.5.1, with 84 of the 98 catalogue figures embedded as data URIs
and the 14 nothing references left out. It is addressed by fragment
(`cpacs-doc.html#/tree/cpacs/vehicles/`), because a browser lets a `file://`
page change nothing else about its URL, and it offers no links to citable pages,
because this form does not write any.

### `serve` — the mode for working on the schema

```
cpacs-doc serve path/to/cpacs/schema/cpacs_schema.xsd
```

Builds the model in memory, serves the viewer on <http://127.0.0.1:8000>, and
rebuilds whenever the schema or the media catalogue changes — the build report
goes to the terminal on every pass and the browser reloads by itself. Nothing is
written to disk. `--host` and `--port` change the address; `--port 0` takes any
free port. Stop it with Ctrl-C.

It reproduces the deployment target rather than merely serving files: one
not-found document answers every path that is not a file, tree paths keep their
address and carry status 404, and there are no directory listings. A generic
static server does not do this, which is why `python -m http.server` is not a
substitute.

---

## 3. The media catalogue converter

`tools/convert_media_catalogue.py` migrates the figure catalogue out of the SHFB
project file (`.shfbproj`) into `media.json`, correcting file name
capitalisation against the file system on the way.

This is a **one-off migration, not part of the build**: run it once, commit the
result, and the `.shfbproj` is no longer needed for figures. The script is
standard library only — no `lxml`, no project environment. It does still need a
working Python interpreter, so type `python` the way your install path spells it
(see the table in section 2): `uv run python …` on Path A, plain `python …` with
the environment activated on Paths B and C. A bare `python` in a fresh Windows
terminal is the one case that will not work.

### Use it

Always look first:

```
python tools/convert_media_catalogue.py path/to/cpacs/documentation --dry-run
```

```
source: Cpacs_doc_project.shfbproj
entries: 98
(dry run, nothing written)
```

Then write:

```
python tools/convert_media_catalogue.py path/to/cpacs/documentation
```

The argument is the directory holding the `.shfbproj` **and** the figures. The
catalogue is written to `<documentation>/media.json`, or wherever `-o` points.

Three things to know before the first real run:

* **It overwrites `media.json` without asking.** Run `--dry-run` first and keep
  the old file in git, so the diff shows what actually changed.
* **It reads exactly one project file** — the alphabetically first `.shfbproj`
  in that directory. The CPACS documentation directory holds two
  (`Cpacs_doc_project.shfbproj` and `Toolspecific_doc_project.shfbproj`), so
  `Cpacs_doc_project.shfbproj` is the one converted; the `source:` line names
  it. To convert the other one, pass a directory containing only that file.
* **Exit status is 1 when entries were dropped**, so a catalogue that came out
  quietly shorter than its source cannot pass unnoticed in a script.

### What it produces

Every `<Image>` entry becomes one catalogue entry, keyed by its `<ImageId>`,
with the file path relative to the documentation directory and
`<AlternateText>` as `alt`. Entries are written in id order:

```json
{
  "schemaVersion": 1,
  "images": {
    "guideCurveIllustration": {
      "file": "figures/GuideCurveDocumentation.png",
      "alt": "Illustration of guide curves"
    },
    "superEllipseLowerZ0": {
      "file": "equations/superEllipseZ0.png",
      "alt": "Equation for superellipse middle line"
    }
  }
}
```

Ids and file names are independent, as both entries show; nothing is inferred
from the one to reach the other.

### What it reports

Every line after `entries:` is a problem or a correction:

| Message | What happened | Entry kept? |
| --- | --- | --- |
| `<id>: case corrected a/B.png -> a/b.png` | The spelling in the project file differs from the file on disk | yes, corrected |
| `<id>: file not found: …` | No file matches, in any capitalisation | no |
| `<id>: no AlternateText; alt is mandatory in media.json` | Missing or empty alt text | no |
| `<id>: declared more than once` | Duplicate `<ImageId>` | first one only |
| `entry without <ImageId>: …` | Image has no id to key on | no |

Only the dropped entries set exit status 1; a corrected capitalisation does not.

File names are compared against the actual directory listing rather than through
`Path.exists()`, which is case-insensitive on Windows and macOS and would accept
the very spellings the conversion exists to correct. Directories are matched
segment by segment, since a directory may differ in case just as a file may. The
practical effect: a figure reference that works on your Windows machine but
breaks on a Linux runner is caught here.

---

## 4. Other tools and notes

### `tools/survey_doc_vocabulary.py`

Counts the documentation vocabulary of a schema and cross-checks the media
catalogue against the file system. Independent of the package, runnable against
any XSD; needs `lxml`, so run it inside the environment:

```
python tools/survey_doc_vocabulary.py path/to/cpacs_schema.xsd --media path/to/documentation
```

### Testing

```
pytest
```

`uv run pytest` on Path A, as everywhere else.

The viewer's keyboard behaviour is checked in a real browser: `tests/cdp.py`
drives an installed Chrome or Edge over the DevTools protocol, without a driver
package and without Node. Those tests skip where no such browser is found, and
`CPACS_DOC_BROWSER` points at one that is installed elsewhere. Everything else
runs without a browser.

### Reporting rather than repairing

Where the schema deviates from its own conventions, the extractor reports and
moves on. It does not recover a documentation body from an unexpected wrapper,
does not infer a figure's file from its id, and does not translate vocabulary it
has not been told about. Silent repair would keep the underlying defect alive
and would oblige every later consumer to reimplement the same guess.

### Where this sits

Stage one of the three-stage architecture (extractor → generator → viewer).
`ddue` markup is carried as plain text; turning it into HTML belongs to the
generator. The extractor deliberately does not depend on `cpacs-schema-tool` or
on the viewer.

---

## 5. How this was built

**This software was written with the assistance of a generative AI system.**
The assistant was Anthropic's Claude, used as a coding assistant from a
terminal, over the development period recorded in the git history.

### What was AI-assisted, and what was not

Assisted: the Python package under `src/`, the viewer's JavaScript and CSS, the
test suite under `tests/`, the tooling under `tools/`, and the planning
documents under `planning/` — including the decision records and this README.

**Not** assisted, and this is the distinction that matters for anyone reading
the output: the documentation content this tool extracts, reports on and
displays is the CPACS schema's own `xsd:documentation`, carried through
unchanged. No description, summary, remark, example or figure caption in the
generated model or in the viewer is written, completed, rewritten or
paraphrased by a model. The extractor reports where the schema's documentation
is missing or malformed and does not fill the gap — see *Reporting rather than
repairing* above, and goal G5 in
`planning/specs/CPACS_Documentation_System_Specification.md`, which makes the
schema the single source of truth.

### Human review and responsibility

Every change was proposed one step at a time, reviewed and accepted by the
maintainers before it entered the repository. The design decisions are the
maintainers' own and are recorded with their reasoning in
`planning/decisions/`. Editorial responsibility for this repository and for the
documentation it produces rests with the copyright holder named in `NOTICE`,
the German Aerospace Center (DLR), Institute of System Architectures in
Aeronautics.

### Relationship to Regulation (EU) 2024/1689 (AI Act)

This statement is voluntary. It is made because readers of a documentation tool
deserve to know how it came about, and not because the Regulation requires it
of this project — as far as we can tell, it does not. Set out plainly, so that
the claim can be checked rather than taken on trust:

- **Art. 50(2)**, marking synthetic output in a machine-readable format, is an
  obligation on the *provider* of the AI system, not on those who use it to
  write software.
- **Art. 50(4)**, the deployer's duty to disclose, covers AI-generated or
  manipulated text *published in order to inform the public on matters of
  public interest*. It also does not apply where the content has undergone
  human review and a natural or legal person holds editorial responsibility for
  it — which is the case here, as stated above.
- The Regulation contains **no general obligation to label software written
  with AI assistance**. A badge claiming conformity where no obligation applies
  would itself be a misleading claim, so none is made.
- The transparency obligations in Art. 50 have applied since 2 August 2026.

The disclosure above is written to satisfy the substance of an Art. 50(4)
disclosure — what was generated, by what, under whose review — should the
Regulation, or a downstream user's own policy, ever call for one.

This is a statement of fact about how the project was built, not legal advice.
Anyone redistributing or building on this work should form their own view of
their obligations.
