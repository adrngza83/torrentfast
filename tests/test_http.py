"""Tests for the segmented HTTP downloader, against a local throttled server."""
import hashlib
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from torrentfast_http import HttpDownload

DATA = os.urandom(12 * 1024 * 1024)
SHA = hashlib.sha256(DATA).hexdigest()
RATE = 1024 * 1024  # 1 MiB/s per connection


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        ranges = self.path.startswith("/r/")
        start, end = 0, len(DATA) - 1
        rng = self.headers.get("Range")
        if ranges and rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else end
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(DATA)}")
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Disposition", 'attachment; filename="test.bin"')
        self.end_headers()
        t0, sent, pos = time.time(), 0, start
        try:
            while pos <= end:
                n = min(65536, end - pos + 1)
                self.wfile.write(DATA[pos:pos + n])
                pos += n
                sent += n
                delay = sent / RATE - (time.time() - t0)
                if delay > 0:
                    time.sleep(delay)
        except OSError:
            pass


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def wait(dl, limit=60):
    t = time.time()
    while dl.status not in ("done", "error", "paused") and time.time() - t < limit:
        time.sleep(0.1)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_segmented_is_faster_and_correct(server, tmp_path):
    t = time.time()
    dl = HttpDownload(server + "/r/a", str(tmp_path / "out"), str(tmp_path), connections=8)
    dl.start()
    wait(dl)
    elapsed = time.time() - t
    assert dl.status == "done", dl.error
    assert dl.name == "test.bin"
    assert sha(dl.path) == SHA
    # 12 MiB at 1 MiB/s per connection: one connection needs ~12 s, eight need ~2 s
    assert elapsed < 8, f"segmented download took {elapsed:.1f}s"


def test_pause_and_resume_after_restart(server, tmp_path):
    out, state = str(tmp_path / "out"), str(tmp_path)
    dl = HttpDownload(server + "/r/b", out, state, connections=2)
    dl.start()
    time.sleep(5)
    dl.pause()
    time.sleep(0.5)
    saved = dl._chunk_bytes()
    assert saved > 0
    again = HttpDownload(server + "/r/b", out, state, connections=8)  # like reopening the app
    assert again.status == "paused" and again.bytes_done == saved
    again.start()
    wait(again)
    assert again.status == "done", again.error
    assert sha(again.path) == SHA


def test_server_without_ranges_uses_one_connection(server, tmp_path):
    dl = HttpDownload(server + "/n/c", str(tmp_path / "out"), str(tmp_path), connections=16)
    dl.start()
    wait(dl)
    assert dl.status == "done" and dl.ranges is False
    assert sha(dl.path) == SHA


def test_delete_never_touches_another_files(server, tmp_path):
    out = str(tmp_path / "out")
    first = HttpDownload(server + "/r/d1", out, str(tmp_path), connections=8)
    first.start()
    wait(first)
    second = HttpDownload(server + "/r/d2", out, str(tmp_path), connections=2)  # same file name
    second.start()
    time.sleep(1)
    second.remove(delete_files=True)
    assert os.path.exists(first.path)
    assert not os.path.exists(second.part)
