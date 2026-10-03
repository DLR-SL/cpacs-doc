"""The development server, exercised over a real socket.

A stub request object would test the routing table but not the property the
mode exists for: that a request behaves the way it will behave once deployed.
Status codes, headers and body all matter here, so the tests speak HTTP.
"""

import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cpacs_doc import serve as serve_module

FIXTURES = Path(__file__).parent / "fixtures"


def get(base: str, path: str):
    """Fetch a path, returning status and body for misses as well as hits."""
    try:
        with urllib.request.urlopen(base + path) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


@pytest.fixture
def site(tmp_path):
    schema = tmp_path / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)
    site = serve_module.Site(
        schema, None, media_expected=False, media_root=tmp_path / "media", limit=0
    )
    assert site.rebuild()
    return site


@pytest.fixture
def base(site):
    server = serve_module.create_server(site, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_a_tree_path_answers_with_the_router_under_status_404(base):
    status, body, headers = get(base, "/tree/cpacs/wings/wing/")
    # 404 is what the deployment target answers for a tree path (§3.4);
    # answering 200 here would hide a broken asset reference until deployment.
    assert status == 404
    assert headers["Content-Type"].startswith("text/html")
    assert b'id="cd-tree"' in body


def test_a_directory_gets_no_listing(base):
    status, body, _ = get(base, "/type/")
    assert status == 404
    assert b'id="cd-tree"' in body


def test_every_served_page_reloads_and_no_generated_one_does(base):
    from cpacs_doc import generator

    for path in ("/tree/cpacs/", "/", "/type/wingType/"):
        assert serve_module.BUILD_ROUTE.encode() in get(base, path)[1], path
    # The generated output is what CI deploys; a poll for an endpoint no static
    # host has must not travel with it.
    assert serve_module.BUILD_ROUTE not in generator.router_html()


def test_the_index_is_served_at_the_root(base):
    status, body, _ = get(base, "/")
    assert status == 200
    assert b"wingType" in body


def test_the_model_is_served_from_memory(base, site):
    status, body, _ = get(base, serve_module.MODEL_ROUTE)
    assert status == 200
    assert body == site.model_bytes


def test_a_type_page_is_rendered_on_demand(base):
    status, body, _ = get(base, "/type/wingType/index.html")
    assert status == 200
    assert b"<h1>wingType</h1>" in body
    # The trailing-slash form is what §4.4 writes and what a static host
    # resolves to index.html.
    assert get(base, "/type/wingType/")[1] == body


def test_an_unknown_type_falls_through_to_the_router(base):
    status, body, _ = get(base, "/type/noSuchType/")
    assert status == 404
    assert b'id="cd-tree"' in body


def test_assets_are_served_and_nothing_else_from_that_directory(base):
    status, body, headers = get(base, "/assets/viewer.js")
    assert status == 200
    assert headers["Content-Type"].startswith("text/javascript")
    assert b'"use strict"' in body
    assert get(base, "/assets/secrets.txt")[0] == 404


def test_media_is_served_from_the_media_root(base, site):
    site.media_root.mkdir(parents=True, exist_ok=True)
    (site.media_root / "figures").mkdir(exist_ok=True)
    (site.media_root / "figures" / "a.png").write_bytes(b"\x89PNG\r\n")
    status, body, headers = get(base, "/media/figures/a.png")
    assert status == 200
    assert body == b"\x89PNG\r\n"
    assert headers["Content-Type"] == "image/png"


def test_a_media_path_leaving_the_root_is_refused(base, site, tmp_path):
    site.media_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    assert get(base, "/media/../outside.txt")[0] == 404
    # Percent-encoded, so no client or proxy can normalise the traversal away
    # before it reaches the guard.
    assert get(base, "/media/%2e%2e/outside.txt")[0] == 404


def test_the_build_counter_rises_with_every_rebuild(base, site):
    first = get(base, serve_module.BUILD_ROUTE)[1]
    site.rebuild()
    assert get(base, serve_module.BUILD_ROUTE)[1] != first


def test_responses_are_not_cached(base):
    assert get(base, "/")[2]["Cache-Control"] == "no-store"


def test_an_unparsable_schema_leaves_the_previous_model_standing(site, capsys):
    before = site.model_bytes
    site.schema.write_text("<xsd:schema", encoding="utf-8")
    assert site.rebuild() is False
    assert site.model_bytes == before
    assert "cannot parse" in capsys.readouterr().err


def test_the_watcher_rebuilds_when_the_schema_changes(site):
    stop = threading.Event()
    rebuilt = threading.Event()
    original = site.rebuild

    def observe():
        try:
            return original()
        finally:
            rebuilt.set()

    site.rebuild = observe
    # The baseline is taken here, not in the thread: otherwise the write below
    # can land before the thread is scheduled, and the change is then part of
    # the state the watcher starts from.
    thread = threading.Thread(
        target=serve_module.watch,
        args=(site, stop, 0.02, serve_module.stamps_of(site)),
        daemon=True,
    )
    thread.start()
    try:
        text = site.schema.read_text(encoding="utf-8")
        site.schema.write_text(text.replace("A wing.", "A wing, changed."), encoding="utf-8")
        assert rebuilt.wait(timeout=10)
    finally:
        stop.set()
        thread.join(timeout=5)
    assert b"A wing, changed." in site.model_bytes



def test_a_change_made_before_the_watcher_runs_is_still_seen(site):
    """The window between deciding to watch and the thread being scheduled is
    not a hole: the baseline belongs to the caller. Taken inside the thread, a
    save landing in that window is read as the state that was always there and
    the change is never seen — windows-latest / 3.10 lost that race in CI."""
    stamps = serve_module.stamps_of(site)
    text = site.schema.read_text(encoding="utf-8")
    site.schema.write_text(text.replace("A wing.", "A wing, changed."), encoding="utf-8")

    stop = threading.Event()
    rebuilt = threading.Event()
    original = site.rebuild

    def observe():
        try:
            return original()
        finally:
            rebuilt.set()

    site.rebuild = observe
    thread = threading.Thread(
        target=serve_module.watch, args=(site, stop, 0.02, stamps), daemon=True
    )
    thread.start()
    try:
        assert rebuilt.wait(timeout=10)
    finally:
        stop.set()
        thread.join(timeout=5)
    assert b"A wing, changed." in site.model_bytes

def test_a_browser_dropping_a_connection_is_not_an_error(site, capsys):
    """A cancelled image, a reload, a navigation away — from here they all look
    like a reset peer. `socketserver` prints a full traceback for each, and in
    a mode whose entire output is the build report that reads like a crash.

    It also matters beyond the noise: those tracebacks are written from daemon
    threads, and one still writing when the interpreter shuts down is a fatal
    error rather than a message.
    """
    server = serve_module.create_server(site, "127.0.0.1", 0)
    try:
        try:
            raise ConnectionResetError("the browser went away")
        except ConnectionResetError:
            server.handle_error(None, ("127.0.0.1", 0))
        assert capsys.readouterr().err == ""

        # Anything else is still a finding.
        try:
            raise ValueError("something the server got wrong")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 0))
        assert "ValueError" in capsys.readouterr().err
    finally:
        server.server_close()


def test_the_access_log_can_be_turned_off(site, capsys):
    """`serve` wants the log; the tests run browsers and want silence, because
    what a handler thread does not write it cannot be killed in the middle of.
    """
    def fetch(quiet):
        server = serve_module.create_server(site, "127.0.0.1", 0, quiet=quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            get(f"http://127.0.0.1:{server.server_address[1]}", "/index.html")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        return capsys.readouterr().err

    assert "GET /index.html" in fetch(quiet=False)
    assert fetch(quiet=True) == ""


def test_a_diagram_path_answers_with_the_router_under_status_404(base):
    """The same bargain as a tree path: the address is kept, and the status
    says there is no file behind it."""
    status, body, headers = get(base, "/diagram/cpacs/wings/wing/")
    assert status == 404
    assert headers["Content-Type"].startswith("text/html")
    assert b'id="cd-diagram"' in body


def test_a_port_already_taken_is_refused_rather_than_shared(site):
    """Windows lets a second socket bind a port another one holds unless the
    server asks for exclusive use, and a second `serve` would then answer half
    of the first one's requests."""
    first = serve_module.create_server(site, "127.0.0.1", 0)
    try:
        with pytest.raises(OSError):
            serve_module.create_server(site, "127.0.0.1", first.server_address[1])
    finally:
        first.server_close()


def test_a_port_already_taken_falls_back_to_a_free_one_when_allowed(site):
    first = serve_module.create_server(site, "127.0.0.1", 0)
    try:
        second = serve_module.create_server(
            site, "127.0.0.1", first.server_address[1], fallback=True
        )
        try:
            assert second.server_address[1] not in (0, first.server_address[1])
        finally:
            second.server_close()
    finally:
        first.server_close()


@pytest.fixture
def served(monkeypatch, tmp_path):
    """Run `cpacs-doc serve` up to the point where it would block, and record
    what it handed to the browser.

    The browser is the one dependency stubbed: opening a real window on every
    test run is a side effect no test should have.
    """
    from cpacs_doc import cli

    opened = []
    monkeypatch.setattr(serve_module.webbrowser, "open", opened.append)
    monkeypatch.setattr(serve_module.Server, "serve_forever",
                        lambda self, *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    schema = tmp_path / "minimal.xsd"
    shutil.copyfile(FIXTURES / "minimal.xsd", schema)

    def run(*options):
        return cli.main(["serve", str(schema), "--no-media", *options]), opened

    return run


def test_open_hands_the_tree_address_to_the_browser(served):
    code, opened = served("--open", "--port", "0")
    assert code == 0
    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:")
    assert opened[0].endswith("/tree/cpacs/")


def test_without_open_no_browser_is_started(served):
    code, opened = served("--port", "0")
    assert code == 0
    assert opened == []


def test_the_default_port_taken_is_not_a_failure(served, monkeypatch, site, capsys):
    taken = serve_module.create_server(site, "127.0.0.1", 0)
    monkeypatch.setattr(serve_module, "DEFAULT_PORT", taken.server_address[1])
    try:
        code, _ = served()
    finally:
        taken.server_close()
    assert code == 0
    assert f":{taken.server_address[1]}/" not in capsys.readouterr().out


def test_a_named_port_taken_is_reported_without_a_traceback(served, site, capsys):
    taken = serve_module.create_server(site, "127.0.0.1", 0)
    try:
        code, _ = served("--port", str(taken.server_address[1]))
    finally:
        taken.server_close()
    assert code == 2
    assert f"port {taken.server_address[1]} is in use" in capsys.readouterr().err
