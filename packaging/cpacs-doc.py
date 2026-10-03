"""Entry script for PyInstaller, which wants a file rather than a module.

Build from the repository root:

    uv run --group dist pyinstaller --onefile --name cpacs-doc --collect-data cpacs_doc packaging/cpacs-doc.py
"""

import sys

from cpacs_doc.launch import main

sys.exit(main())
