"""The development server (R4): the deployment target's behaviour, on localhost.

Nothing is written to disk. The model is built in memory and re-built when the
schema changes; type pages are rendered per request, which costs 0.1 ms for the
largest of them and saves the 1,309 files a full `build --site` produces.

What matters here is fidelity, not convenience. Three properties of the
deployment target are reproduced deliberately, because a development mode that
diverges from them hides exactly the defects it exists to surface (§3.4, §3.5):

* one not-found document serves every path that is not a file,
* a tree path answers with HTTP status 404 while keeping its address,
* there are no directory listings — this handler serves the routes below and
  nothing else, which is why it does not derive from SimpleHTTPRequestHandler.
"""

from __future__ import annotations

import json
import mimetypes
import sys
import threading
import time
import urllib.parse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lxml import etree

from . import generator, model as model_module
from .findings import Report

MODEL_ROUTE = "/cpacs-doc-model.json"
BUILD_ROUTE = "/_cpacs-doc/build"
ASSET_ROUTE = f"/{generator.ASSET_DIRECTORY}/"
MEDIA_ROUTE = f"/{generator.MEDIA_DIRECTORY}/"
TYPE_ROUTE = f"/{generator.TYPES_DIRECTORY}/"

# mimetypes consults the Windows registry, so its answers are a property of the
# developer's machine rather than of this program. The handful of types the
# viewer actually needs are stated outright.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}

# Injected into every HTML response this server sends, and into none of the
# generated output — deployed pages would poll an endpoint that exists on no
# static host. Polling rather than EventSource: a stream would hold a thread per
# open tab and make Ctrl-C wait for it, while one request per second costs
# nothing over a loopback socket.
LIVE_RELOAD = """<script>
(function () {
  "use strict";
  var current = null;
  window.setInterval(function () {
    fetch("%s", { cache: "no-store" })
      .then(function (response) { return response.ok ? response.text() : null; })
      .then(function (generation) {
        if (generation === null) return;
        if (current === null) current = generation;
        else if (generation !== current) window.location.reload();
      })
      .catch(function () {});
  }, 1000);
}());
</script>
</body>
""" % BUILD_ROUTE

BODY_END = "</body>"

WATCH_INTERVAL = 0.5


def with_live_reload(html: str) -> str:
    """Append the reload script to a page the generator produced unchanged.

    Done here rather than in the generator so that what CI deploys and what the
    tests compare against stay free of development machinery.
    """
    return html.replace(BODY_END, LIVE_RELOAD, 1) if BODY_END in html else html + LIVE_RELOAD


def _stamp(path: Path):
    """Modification time and size, or None where the file is currently absent.

    An editor that writes by rename makes the file vanish for an instant; that
    is a state to wait through, not one to rebuild on.
    """
    try:
        status = path.stat()
    except OSError:
        return None
    return status.st_mtime_ns, status.st_size


class Site:
    """The model, and the one operation that replaces it.

    Only two files are watched. That is complete rather than approximate: the
    extractor parses a single schema file and reports `xsd:include`, `import`,
    `redefine` and `override` as errors instead of following them
    (catalogue.py), so no second schema file can exist unnoticed.
    """

    def __init__(self, schema: Path, media_path: Path | None, *,
                 media_expected: bool, media_root: Path | None, limit: int | None):
        self.schema = Path(schema)
        self.media_path = Path(media_path) if media_path else None
        self.media_expected = media_expected
        self._configured_media_root = Path(media_root) if media_root else None
        self.limit = limit

        self._lock = threading.Lock()
        self.generation = 0
        self.model: dict = {}
        self.model_bytes = b""
        self.media_root: Path | None = self._configured_media_root

    @property
    def watched(self) -> list[Path]:
        return [p for p in (self.schema, self.media_path) if p is not None]

    def rebuild(self) -> bool:
        """Build a new model, swapping it in only once it is complete.

        A schema that does not parse is the normal state of a file being
        edited, not an occasion to stop serving: the failure is reported and
        the previous model stays in place.
        """
        # Imported here rather than at module scope: cli imports this module to
        # register the subcommand, and the pipeline lives in cli.
        from .cli import root_version, run

        report = Report()
        started = time.perf_counter()
        try:
            catalogue, tree, media_catalogue, content_by_type = run(
                self.schema, self.media_path, report, media_expected=self.media_expected
            )
            rendered, render_findings = model_module.render_all(
                catalogue, media_catalogue, self.schema.name
            )
            report.extend(render_findings)
            model = model_module.build(
                catalogue,
                tree,
                media_catalogue,
                report,
                schema_path=str(self.schema),
                schema_version=root_version(self.schema, report),
                content_by_type=content_by_type,
                rendered=rendered,
            )
        except etree.XMLSyntaxError as error:
            print(f"cannot parse {self.schema}: {error}", file=sys.stderr)
            return False

        payload = json.dumps(model, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with self._lock:
            self.model = model
            self.model_bytes = payload
            self.generation += 1
            if self._configured_media_root is None and media_catalogue is not None:
                self.media_root = media_catalogue.base_dir

        report.write(sys.stdout, limit=self.limit)
        statistics = model.get("statistics", {})
        print(
            f"\nbuild {self.generation}: {statistics.get('types', 0)} types, "
            f"{statistics.get('treeNodes', 0)} tree nodes, "
            f"{len(payload) / 1e6:.1f} MB model, "
            f"{time.perf_counter() - started:.1f} s"
        )
        return True

    def snapshot(self) -> tuple[int, dict, bytes]:
        with self._lock:
            return self.generation, self.model, self.model_bytes

    def root_element(self) -> str:
        """Name of the root element, for the address printed at startup."""
        _, model, _ = self.snapshot()
        tree = model.get("tree")
        if not tree:
            return ""
        return model.get("declarations", {}).get(tree.get("d"), {}).get("name", "")


def watch(site: Site, stop: threading.Event, interval: float = WATCH_INTERVAL) -> None:
    stamps = {path: _stamp(path) for path in site.watched}
    while not stop.wait(interval):
        for path in site.watched:
            current = _stamp(path)
            if current is None or current == stamps[path]:
                continue
            stamps[path] = current
            print(f"\n{path} changed, rebuilding")
            site.rebuild()
            # One rebuild covers every watched file; re-read the rest so a
            # simultaneous change does not trigger a second, identical build.
            stamps = {p: _stamp(p) for p in site.watched}
            break


class Handler(BaseHTTPRequestHandler):
    server_version = "cpacs-doc"
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, site: Site, **kwargs):
        self.site = site
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 — name fixed by BaseHTTPRequestHandler
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)

        if path == BUILD_ROUTE:
            self._send(str(self.site.generation).encode("ascii"), "text/plain; charset=utf-8")
        elif path == "/" or path == "/index.html":
            self._send(self._index(), CONTENT_TYPES[".html"])
        elif path == MODEL_ROUTE:
            self._send(self.site.snapshot()[2], CONTENT_TYPES[".json"])
        elif path.startswith(ASSET_ROUTE):
            self._asset(path[len(ASSET_ROUTE):])
        elif path.startswith(MEDIA_ROUTE):
            self._media(path[len(MEDIA_ROUTE):])
        elif path.startswith(TYPE_ROUTE):
            self._type_page(path[len(TYPE_ROUTE):])
        else:
            self._router()

    def _index(self) -> bytes:
        _, model, _ = self.site.snapshot()
        html = generator.index_html(
            model.get("types", {}), model.get("statistics", {}), model.get("meta", {})
        )
        return with_live_reload(html).encode("utf-8")

    def _asset(self, name: str) -> None:
        if name not in generator.ASSET_FILES:
            self._router()
            return
        content_type = CONTENT_TYPES.get(Path(name).suffix, "application/octet-stream")
        self._send(generator.asset(name).encode("utf-8"), content_type)

    def _media(self, relative: str) -> None:
        root = self.site.media_root
        if root is None or not relative:
            self._router()
            return
        target = (root / relative).resolve()
        # A request may name any path it likes; only what lies under the media
        # root is answered.
        if not target.is_file() or not target.is_relative_to(root.resolve()):
            self._router()
            return
        suffix = target.suffix.lower()
        content_type = CONTENT_TYPES.get(suffix) or mimetypes.guess_type(target.name)[0]
        self._send(target.read_bytes(), content_type or "application/octet-stream")

    def _type_page(self, remainder: str) -> None:
        slug = remainder.rstrip("/")
        if slug.endswith("/index.html"):
            slug = slug[: -len("/index.html")]
        name = generator.unslug(slug)
        _, model, _ = self.site.snapshot()
        types = model.get("types", {})
        if name not in types:
            self._router()
            return
        html = generator.type_page(name, types[name], types, model.get("firstPaths", {}))
        self._send(with_live_reload(html).encode("utf-8"), CONTENT_TYPES[".html"])

    def _router(self) -> None:
        """What the deployment target answers for everything that is not a file.

        Status 404 is the point, not an oversight: it is what a tree path
        carries on GitHub Pages (§3.4), and serving 200 here would let a broken
        asset reference pass unnoticed until deployment.
        """
        html = generator.router_html()
        self._send(with_live_reload(html).encode("utf-8"), CONTENT_TYPES[".html"], status=404)

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # A rebuild must reach the browser on the next request, not after the
        # cache expires.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        # The build poll fires once per second per tab and would bury the build
        # report, which is the output this mode exists to show (R4).
        if getattr(self, "path", "").split("?")[0] == BUILD_ROUTE:
            return
        sys.stderr.write(f"{format % args}\n")


def create_server(site: Site, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), partial(Handler, site=site))
    server.daemon_threads = True
    return server


def serve(schema: Path, media_path: Path | None, *, media_expected: bool,
          media_root: Path | None, limit: int | None, host: str, port: int) -> int:
    site = Site(
        schema,
        media_path,
        media_expected=media_expected,
        media_root=media_root,
        limit=limit,
    )
    if not site.rebuild():
        return 2

    server = create_server(site, host, port)
    stop = threading.Event()
    watcher = threading.Thread(target=watch, args=(site, stop), daemon=True)
    watcher.start()

    address = f"http://{host}:{server.server_address[1]}"
    root = site.root_element()
    print(f"\nserving {address}/" + (f"tree/{root}/" if root else ""))
    print(f"type index {address}/  |  Ctrl-C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        stop.set()
        server.server_close()
    return 0
