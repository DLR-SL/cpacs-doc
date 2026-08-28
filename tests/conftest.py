import shutil
import threading
from pathlib import Path

import pytest
from lxml import etree

import cdp

from cpacs_doc import serve as serve_module

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parse():
    """Parse a fixture schema and return its root element."""

    def _parse(name: str):
        return etree.parse(str(FIXTURES / name)).getroot()

    return _parse


@pytest.fixture(scope="session")
def browser(tmp_path_factory):
    """One headless browser for the session; every module navigates the same tab.

    Starting one costs about a second and a navigation a tenth of that, so the
    modules share it rather than each paying for its own.
    """
    executable = cdp.find_browser()
    if executable is None:
        pytest.skip("no Chrome or Edge on this machine")
    driver = cdp.Browser(executable)
    driver.start(tmp_path_factory.mktemp("profile"))
    yield driver
    driver.close()


@pytest.fixture(scope="module")
def base(request, tmp_path_factory, browser):
    """The viewer, served the way it is deployed (§3.4, R4).

    Which schema is the module's own business: it says so with a `SCHEMA`
    constant at its top. Each module gets its own port, and therefore its own
    origin and its own local storage.
    """
    name = getattr(request.module, "SCHEMA", "minimal.xsd")
    directory = tmp_path_factory.mktemp("site")
    schema = directory / name
    shutil.copyfile(FIXTURES / name, schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=directory / "media", limit=0
    )
    assert site.rebuild()
    # Quiet: a browser leaves connections behind, and a daemon thread still
    # writing to stderr when the interpreter shuts down is a fatal error
    # rather than a test failure — Windows CI showed exactly that.
    server = serve_module.create_server(site, "127.0.0.1", 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_address[1]}"
    assert cdp.reachable(address + "/tree/cpacs/"), "the development server did not answer"
    yield address
    # Send the browser away first. Its keep-alive connections each hold a
    # handler thread blocked on a read, and a daemon thread that outlives the
    # server outlives the interpreter too.
    browser.open("about:blank")
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
