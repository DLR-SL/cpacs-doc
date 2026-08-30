"""The browser driver's own start-up, without a browser.

Everything else that uses `cdp` needs Chrome or Edge and skips without one.
This does not: what it holds is the one step that runs before any of them, and
that took every browser test on windows-latest with it when it failed.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

import cdp


@pytest.fixture
def profile(tmp_path):
    directory = tmp_path / "profile"
    directory.mkdir()
    return directory


def test_the_port_is_read_once_the_browser_has_written_it(profile):
    driver = cdp.Browser("none", timeout=5.0)

    def write():
        time.sleep(0.2)
        (profile / "DevToolsActivePort").write_text("9222\n/devtools/browser/x\n")

    threading.Thread(target=write, daemon=True).start()
    assert driver._endpoint(profile) == (9222, "/devtools/browser/x")


def test_a_marker_that_cannot_be_read_yet_is_waited_out(profile):
    """The marker exists from the moment the browser creates it. Opening it
    while it is still being written raises on Windows — errno 13, a sharing
    violation, not the errno 2 that `exists()` guards against — and the fixture
    then failed for every browser test in the session."""
    marker = profile / "DevToolsActivePort"
    # A directory stands in for the file the browser holds open: reading it
    # raises an OSError on both platforms, which is what has to be waited out.
    marker.mkdir()
    driver = cdp.Browser("none", timeout=5.0)

    def replace():
        time.sleep(0.2)
        marker.rmdir()
        marker.write_text("9333\n/devtools/browser/y\n")

    threading.Thread(target=replace, daemon=True).start()
    assert driver._endpoint(profile) == (9333, "/devtools/browser/y")


def test_a_browser_that_never_writes_one_is_given_up_on(profile):
    driver = cdp.Browser("none", timeout=0.3)
    with pytest.raises(TimeoutError):
        driver._endpoint(profile)
