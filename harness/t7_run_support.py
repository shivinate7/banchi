"""What T7's `run` does around its checks: a spawn refusal, progress lines and a refused network.

Kept beside the harness, not in `harness/tests/t7_store_and_seams.py`, so `run` stays a loop. The
cases that pin each half are `harness/tests/t7/network_refusal.py` and `harness/tests/t7/run_lines.py`.

Cost: no thread and no process. A progress line is one flushed stderr write per check, and the
network refusal wraps five connect functions for the length of one `run`, then puts them back.
"""

from __future__ import annotations

import http.client
import ipaddress
import multiprocessing
import os
import socket
import sys
import urllib.parse
import urllib.request
from contextlib import contextmanager
from typing import Iterator

# What a child process must still reach directly: every fake portal and the capture server listen here.
LOOPBACK_HOSTS = "localhost,127.0.0.1,::1"
PROXY_VARIABLES = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")
BYPASS_VARIABLES = ("NO_PROXY", "no_proxy")

_current_check = ["(no check)"]
# A refused call is retried by product code, so a line is printed once per check and host.
_told: set = set()


def in_spawned_child() -> bool:
    """True inside a `multiprocessing` child. `parent_process()` is None while a spawn child imports
    its main module, so the process's name is the answer that holds at that moment too."""
    return multiprocessing.current_process().name != "MainProcess"


def progress(line: str) -> None:
    """One flushed stderr line, so a watcher of a long run sees it as it happens."""
    print(line, file=sys.stderr, flush=True)


def name_check(name: str) -> None:
    """The check whose network calls a refusal line names."""
    _current_check[0] = name
    _told.clear()


def _is_local(host: object) -> bool:
    text = str(host).strip("[]").lower()
    if text == "localhost" or text.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(text.split("%")[0])
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _refuse_unless_local(host: object) -> None:
    if host is not None and not _is_local(host):
        if (_current_check[0], str(host)) not in _told:
            _told.add((_current_check[0], str(host)))
            progress(f"T7 network refused: {_current_check[0]} -> {host}")
        raise ConnectionRefusedError(f"T7 refuses network to {host}: only this machine answers during a run")


@contextmanager
def _children_route_nowhere() -> Iterator[None]:
    """Proxy variables aimed at a loopback port that refuses, and loopback bypassed.

    The port is bound and never listened on, so a connect to it is refused. The socket stays open
    for the run so no other process can take the port.
    """
    parked = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    parked.bind(("127.0.0.1", 0))
    route = f"http://127.0.0.1:{parked.getsockname()[1]}"
    before = {name: os.environ.get(name) for name in PROXY_VARIABLES + BYPASS_VARIABLES}
    try:
        for name in PROXY_VARIABLES:
            os.environ[name] = route
        for name in BYPASS_VARIABLES:
            os.environ[name] = LOOPBACK_HOSTS
        yield
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        parked.close()


@contextmanager
def refused_network() -> Iterator[None]:
    """For the length of the block, a call to a host that is not this machine is refused.

    In process, five doors are wrapped: urllib's `do_open` (it sees the real URL even when a proxy
    is set), `http.client`'s connect (a tunnelled request's real host), `socket.create_connection`
    (the host name before lookup) and the socket's own connect and connect_ex. Each prints one
    line naming the check and the host, then raises `ConnectionRefusedError`, which product code
    reads as an offline host. Child processes inherit proxy variables that go nowhere.
    """
    real_do_open = urllib.request.AbstractHTTPHandler.do_open
    real_http_connect = http.client.HTTPConnection.connect
    real_create_connection = socket.create_connection
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def do_open(self, http_class, req, **kw):
        _refuse_unless_local(urllib.parse.urlsplit(req.full_url).hostname)
        return real_do_open(self, http_class, req, **kw)

    def http_connect(self):
        _refuse_unless_local(self._tunnel_host or self.host)
        return real_http_connect(self)

    def create_connection(address, *args, **kw):
        _refuse_unless_local(address[0])
        return real_create_connection(address, *args, **kw)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _refuse_unless_local(address[0])
        return real_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _refuse_unless_local(address[0])
        return real_connect_ex(self, address)

    with _children_route_nowhere():
        urllib.request.AbstractHTTPHandler.do_open = do_open
        http.client.HTTPConnection.connect = http_connect
        socket.create_connection = create_connection
        socket.socket.connect = connect
        socket.socket.connect_ex = connect_ex
        try:
            yield
        finally:
            urllib.request.AbstractHTTPHandler.do_open = real_do_open
            http.client.HTTPConnection.connect = real_http_connect
            socket.create_connection = real_create_connection
            socket.socket.connect = real_connect
            socket.socket.connect_ex = real_connect_ex
