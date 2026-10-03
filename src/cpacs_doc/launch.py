"""Entry point of the Windows executable.

The executable is started by double click, by dropping a schema on it or by
"Open with" in the Explorer, and only from a terminal with a subcommand. The
first three mean one thing — show this schema — so a lone schema path, or none
at all, becomes `serve <schema> --open`. Anything else is the CLI unchanged.

The console window that comes with the executable is the server's: it shows
the build report on every rebuild, and closing it stops the server.
"""

from __future__ import annotations

import sys

from . import cli


def main(argv: list[str] | None = None, *, run=cli.main, choose=None, pause=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    choose = choose or ask_for_schema
    pause = pause or wait_for_enter

    if argv and (argv[0].startswith("-") or argv[0] in cli.SUBCOMMANDS):
        return run(argv)

    if not argv:
        chosen = choose()
        if not chosen:
            return 0
        argv = [chosen]

    code = run(["serve", *argv, "--open"])
    if code != 0:
        pause()
    return code


def ask_for_schema() -> str | None:
    """A file dialog; `tkinter` ships with Python, so it costs no dependency."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    try:
        return filedialog.askopenfilename(
            title="cpacs-doc: open a schema",
            filetypes=[("XML Schema", "*.xsd"), ("All files", "*.*")],
        ) or None
    finally:
        root.destroy()


def wait_for_enter() -> None:
    try:
        input("\npress Enter to close")
    except EOFError:
        pass


if __name__ == "__main__":
    sys.exit(main())
