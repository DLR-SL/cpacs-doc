"""A browser, driven over the DevTools protocol, with nothing installed.

The viewer's keyboard behaviour is the one part of the system that cannot be
judged without a browser. A DOM stand-in gets the logic right and still misses
a stylesheet rule that hides the cursor, because it has no computed styles, no
real focus and no real key events — which is exactly how the cursor came to be
invisible while the arrow keys were moving it.

The protocol is spoken directly rather than through a driver package. What a
CDP session needs of WebSocket is a hundred lines, and paying that once keeps
the test tooling at pytest and the dependency list at `lxml` (N14, E4).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Chrome and Edge speak the same protocol; either will do.
WINDOWS_CANDIDATES = (
    r"{ProgramFiles}\Google\Chrome\Application\chrome.exe",
    r"{ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    r"{ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    r"{ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
    r"{LOCALAPPDATA}\Google\Chrome\Application\chrome.exe",
)
POSIX_CANDIDATES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "microsoft-edge", "microsoft-edge-stable",
)
MACOS_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

# The keys the viewer handles. `key` alone is not enough: a page sees the code
# and the virtual key of a real press, and taking that shortcut would leave the
# test one step further from what a reader does.
KEYS = {
    "ArrowDown": (40, "ArrowDown"), "ArrowUp": (38, "ArrowUp"),
    "ArrowLeft": (37, "ArrowLeft"), "ArrowRight": (39, "ArrowRight"),
    "Home": (36, "Home"), "End": (35, "End"),
    "Enter": (13, "Enter"), "Escape": (27, "Escape"),
    "Tab": (9, "Tab"), " ": (32, "Space"), "/": (191, "Slash"),
}


def find_browser() -> str | None:
    """The browser to drive, or None when the machine has none."""
    configured = os.environ.get("CPACS_DOC_BROWSER")
    if configured:
        return configured if Path(configured).exists() else None
    if sys.platform == "win32":
        for template in WINDOWS_CANDIDATES:
            path = template.format_map(_Environment())
            if Path(path).exists():
                return path
        return None
    if sys.platform == "darwin":
        for path in MACOS_CANDIDATES:
            if Path(path).exists():
                return path
    for name in POSIX_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


class _Environment(dict):
    """`str.format_map` over the environment, tolerating what is not set."""

    def __missing__(self, key: str) -> str:
        return os.environ.get(key, "__unset__")  # a path that cannot exist


class WebSocket:
    """Enough of RFC 6455 to carry a CDP session: text frames, one at a time."""

    def __init__(self, host: str, port: int, path: str, timeout: float = 30.0):
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(timeout)
        self._stream = self._socket.makefile("rb")
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        self._socket.sendall((
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii"))
        status = self._stream.readline()
        if b"101" not in status:
            raise ConnectionError(f"the browser refused the upgrade: {status!r}")
        while self._stream.readline() not in (b"\r\n", b"\n", b""):
            pass

    def send(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])  # final frame, text
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 1 << 16:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        # A client must mask; a server must not.
        mask = os.urandom(4)
        header += mask
        self._socket.sendall(bytes(header) + bytes(
            byte ^ mask[i % 4] for i, byte in enumerate(payload)
        ))

    def receive(self) -> str:
        while True:
            final, opcode, data = self._frame()
            if opcode == 0x9:                      # ping
                self._control(0xA, data)
                continue
            if opcode == 0x8:                      # close
                raise ConnectionError("the browser closed the connection")
            if opcode not in (0x0, 0x1):           # binary, pong
                continue
            chunks = [data]
            while not final:
                final, _, more = self._frame()
                chunks.append(more)
            return b"".join(chunks).decode("utf-8")

    def close(self) -> None:
        try:
            self._control(0x8, b"")
        except OSError:
            pass
        self._stream.close()
        self._socket.close()

    def _control(self, opcode: int, data: bytes) -> None:
        mask = os.urandom(4)
        self._socket.sendall(bytes([0x80 | opcode, 0x80 | len(data)]) + mask + bytes(
            byte ^ mask[i % 4] for i, byte in enumerate(data)
        ))

    def _frame(self) -> tuple[bool, int, bytes]:
        head = self._read(2)
        final = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        masked = bool(head[1] & 0x80)
        length = head[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read(8))[0]
        key = self._read(4) if masked else b""
        data = self._read(length)
        if masked:
            data = bytes(byte ^ key[i % 4] for i, byte in enumerate(data))
        return final, opcode, data

    def _read(self, count: int) -> bytes:
        data = self._stream.read(count)
        if data is None or len(data) != count:
            raise ConnectionError("the connection ended mid-frame")
        return data


class Browser:
    """A headless browser and one attached tab."""

    def __init__(self, executable: str, timeout: float = 30.0):
        self.timeout = timeout
        self._process: subprocess.Popen | None = None
        self._socket: WebSocket | None = None
        self._session: str | None = None
        self._next = 0
        self._executable = executable

    def start(self, profile: Path) -> None:
        self._process = subprocess.Popen(
            [
                self._executable,
                "--headless=new",
                "--disable-gpu",
                # CI runners often have no usable sandbox; this is a throwaway
                # profile serving one local page.
                "--no-sandbox",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-background-networking",
                "--window-size=1200,900",
                # Port 0: the browser picks one and writes it into the profile,
                # so parallel runs cannot collide over a fixed port.
                "--remote-debugging-port=0",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        port, path = self._endpoint(profile)
        self._socket = WebSocket("127.0.0.1", port, path, timeout=self.timeout)

    def _endpoint(self, profile: Path) -> tuple[int, str]:
        marker = profile / "DevToolsActivePort"
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if marker.exists():
                lines = marker.read_text(encoding="utf-8").splitlines()
                if len(lines) >= 2:
                    return int(lines[0]), lines[1]
            if self._process and self._process.poll() is not None:
                raise RuntimeError("the browser stopped before it was ready")
            time.sleep(0.05)
        raise TimeoutError("the browser did not open a debugging port")

    def open(self, url: str) -> None:
        """Navigate the tab, attaching one the first time round."""
        if self._session is None:
            target = self.command("Target.createTarget", {"url": "about:blank"})
            attached = self.command(
                "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
            )
            self._session = attached["sessionId"]
            self.command("Page.enable")
            self.command("Runtime.enable")
        self.command("Page.navigate", {"url": url})
        # Navigation answers when the document is committed, not when its
        # stylesheet is in force. A test that measures or clicks before then
        # sees an unlaid-out page — which is subtle, machine-dependent, and
        # cost a CI run once already.
        self.wait_for("return document.readyState === 'complete';", "the document")

    def command(self, method: str, params: dict | None = None) -> dict:
        assert self._socket is not None, "the browser was not started"
        self._next += 1
        message = {"id": self._next, "method": method, "params": params or {}}
        if self._session:
            message["sessionId"] = self._session
        self._socket.send(json.dumps(message))
        while True:
            # Commands are issued one at a time, so anything that is not this
            # answer is an event and of no interest here.
            answer = json.loads(self._socket.receive())
            if answer.get("id") != self._next:
                continue
            if "error" in answer:
                raise RuntimeError(f"{method}: {answer['error']}")
            return answer.get("result", {})

    def evaluate(self, expression: str):
        """Run a function body in the page and return what it returns."""
        result = self.command("Runtime.evaluate", {
            "expression": "(function(){" + expression + "})()",
            "returnByValue": True,
            "awaitPromise": True,
        })
        if "exceptionDetails" in result:
            detail = result["exceptionDetails"]
            raise RuntimeError(detail.get("exception", {}).get("description", str(detail)))
        return result.get("result", {}).get("value")

    def press(self, key: str) -> None:
        code, name = KEYS[key]
        common = {
            "key": key,
            "code": name,
            "windowsVirtualKeyCode": code,
            "nativeVirtualKeyCode": code,
        }
        self.command("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common})
        self.command("Input.dispatchKeyEvent", {"type": "keyUp", **common})

    def click(self, x: float, y: float) -> None:
        for kind in ("mousePressed", "mouseReleased"):
            self.command("Input.dispatchMouseEvent", {
                "type": kind, "x": x, "y": y, "button": "left", "clickCount": 1,
            })

    def wait_for(self, expression: str, what: str = "the page") -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                if self.evaluate(expression):
                    return
            except RuntimeError:
                pass  # the document may not be there yet
            time.sleep(0.05)
        raise TimeoutError(f"{what} did not appear")

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()


def reachable(url: str, timeout: float = 10.0) -> bool:
    """Whether the local server answers at all; a 404 counts, tree paths are."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except urllib.error.HTTPError:
            return True
        except OSError:
            time.sleep(0.05)
    return False
