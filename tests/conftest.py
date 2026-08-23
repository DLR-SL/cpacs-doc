from pathlib import Path

import pytest
from lxml import etree

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parse():
    """Parse a fixture schema and return its root element."""

    def _parse(name: str):
        return etree.parse(str(FIXTURES / name)).getroot()

    return _parse
