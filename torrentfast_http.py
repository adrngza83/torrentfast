"""
Segmented HTTP/HTTPS downloader (IDM / aria2 style), standard library only.

A file is split into chunks; N worker connections pull chunks from a shared queue, so fast
connections do more of the work. Progress is saved to a sidecar state file and a download
resumes from the completed chunks after a pause or restart.
"""
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

CHUNK = 4 * 1024 * 1024          # 4 MiB work units
READ = 256 * 1024                # socket read size
UA = "TorrentFast/1.3.0 (+https://github.com/adrngza83/torrentfast)"
_OPENER = None


def _opener():
    # honor the system proxy for internet downloads (unlike the local API)
    global _OPENER
    if _OPENER is None:
        _OPENER = urllib.request.build_opener()
    return _OPENER


def _filename(url, headers):
    cd = headers.get("Content-Disposition") or ""
    m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
    name = urllib.parse.unquote(m.group(1).strip()) if m else ""
    if not name:
        name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path)) or "download"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "download"
    return name[:180]


def probe(url, timeout=15):
    """Return (final_url, size or None, supports_ranges, filename)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with _opener().open(req, timeout=timeout) as r:
        final = r.geturl()
        headers = r.headers
        if r.status == 206:
            m = re.search(r"/(\d+)$", headers.get("Content-Range", ""))
            size = int(m.group(1)) if m else None
            return final, size, size is not None, _filename(final, headers)
        size = headers.get("Content-Length")
        return final, int(size) if size and size.isdigit() else None, False, _filename(final, headers)


class HttpDownload:
    def __init__(self, url, save_dir, state_dir, connections=16, on_change=None):
        self.url = url
        self.save_dir = save_dir
        self.connections = max(1, min(int(connections), 32))
        self.id = "http-" + hashlib.sha1(url.encode()).hexdigest()[:16]
        self.state_file = os.path.join(state_dir, self.id + ".json")
        self.on_change = on_change
        self.name = _filename(url, {})
        self.size = None
        self.ranges = False
        self.final_url = url
        self.done_chunks = set()
        self.bytes_done = 0           # bytes in fully finished chunks + in-flight bytes
        self.status = "queued"        # queued | probing | downloading | paused | done | error
        self.error = ""
        self.active = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = []
        self._rate = 0.0
        self._last = (time.time(), 0)
        self._load()

    # ---------- persistence ----------
    @property
    def path(self):
        return os.path.join(self.save_dir, self.name)

    @property
    def part(self):
        return self.path + ".part"

    def _load(self):
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, encoding="utf-8") as f:
                s = json.load(f)
            self.name, self.size, self.ranges = s["name"], s["size"], s["ranges"]
            self.final_url, self.save_dir = s.get("final_url", self.url), s.get("save_dir", self.save_dir)
            self.done_chunks = set(s.get("done", []))
            self.status = "done" if s.get("finished") else "paused" if s.get("paused") else "queued"
            self.bytes_done = self.size if self.status == "done" and self.size else self._chunk_bytes()
        except (OSError, ValueError, KeyError):
            pass

    def _save(self):
        s = {"url": self.url, "final_url": self.final_url, "name": self.name, "size": self.size,
             "ranges": self.ranges, "save_dir": self.save_dir, "done": sorted(self.done_chunks),
             "finished": self.status == "done", "paused": self.status == "paused"}
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(s, f)
        os.replace(tmp, self.state_file)

    def _nchunks(self):
        return (self.size + CHUNK - 1) // CHUNK if self.size else 1

    def _chunk_bytes(self):
        if not self.size:
            return 0
        n = self._nchunks()
        return sum(min(CHUNK, self.size - i * CHUNK) for i in self.done_chunks if i < n)

    # ---------- control ----------
    def start(self):
        if self.status in ("downloading", "probing", "done"):
            return
        self._stop.clear()
        self.status, self.error = "queued", ""
        t = threading.Thread(target=self._run, daemon=True)
        self._threads = [t]
        t.start()

    def pause(self):
        if self.status in ("done",):
            return
        self._stop.set()
        self.status = "paused"
        self._save()

    def stop(self):
        """Stop for app shutdown; it resumes on next launch (unlike pause)."""
        if self.status in ("downloading", "probing", "queued"):
            self._stop.set()
            for t in self._threads:
                t.join(timeout=5)
            self.status = "queued"
            self._save()

    def remove(self, delete_files=False):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=3)
        finished = self.status == "done"
        doomed = [self.state_file]
        if not finished:
            doomed.append(self.part)       # an unfinished part is useless once removed
        elif delete_files:
            doomed.append(self.path)       # only delete the file this download produced
        for p in doomed:
            try:
                os.remove(p)
            except OSError:
                pass

    # ---------- work ----------
    def _run(self):
        try:
            if self.size is None or not self.done_chunks:
                self.status = "probing"
                self.final_url, self.size, self.ranges, name = probe(self.url)
                if not self.done_chunks:
                    self.name = name
                self._save()
            os.makedirs(self.save_dir, exist_ok=True)
            self.status = "downloading"
            if self.ranges and self.size:
                self._run_segmented()
            else:
                self._run_single()
            if self._stop.is_set():
                return
            part = self.part  # capture before a rename changes self.name
            if os.path.exists(self.path):
                base, ext = os.path.splitext(self.name)
                i = 1
                while os.path.exists(os.path.join(self.save_dir, f"{base} ({i}){ext}")):
                    i += 1
                self.name = f"{base} ({i}){ext}"
            os.replace(part, self.path)
            self.status = "done"
            self.bytes_done = self.size or self.bytes_done
            self._save()
        except Exception as e:  # report any failure in the UI
            if not self._stop.is_set():
                self.status, self.error = "error", str(e)[:200]
        finally:
            self.active = 0
            if self.on_change:
                self.on_change()

    def _run_single(self):
        self.done_chunks.clear()
        self.bytes_done = 0
        req = urllib.request.Request(self.final_url, headers={"User-Agent": UA})
        with _opener().open(req, timeout=30) as r, open(self.part, "wb") as f:
            self.active = 1
            while not self._stop.is_set():
                b = r.read(READ)
                if not b:
                    break
                f.write(b)
                with self._lock:
                    self.bytes_done += len(b)
        if self.size is None:
            self.size = self.bytes_done

    def _run_segmented(self):
        n = self._nchunks()
        if not os.path.exists(self.part) or os.path.getsize(self.part) != self.size:
            if not os.path.exists(self.part):
                self.done_chunks.clear()
            with open(self.part, "ab") as f:
                f.truncate(self.size)  # preallocate
        self.bytes_done = self._chunk_bytes()
        todo = [i for i in range(n) if i not in self.done_chunks]
        q_lock = threading.Lock()
        errors = []

        def worker():
            with open(self.part, "r+b") as f:
                while not self._stop.is_set():
                    with q_lock:
                        if not todo:
                            return
                        i = todo.pop(0)
                    start = i * CHUNK
                    end = min(self.size, start + CHUNK) - 1
                    got = 0
                    holder = [0]
                    for attempt in range(5):
                        try:
                            got = self._fetch(f, start + got, end, got, holder)
                            break
                        except Exception as e:  # retry with backoff, keep partial bytes
                            if self._stop.is_set():
                                return
                            if attempt == 4:
                                errors.append(str(e))
                                with q_lock:
                                    todo.append(i)
                                return
                            got = holder[0]
                            time.sleep(1 + attempt)
                    if self._stop.is_set() and got < end - start + 1:
                        with self._lock:
                            self.bytes_done -= got
                        return
                    with self._lock:
                        self.done_chunks.add(i)
                    if len(self.done_chunks) % 8 == 0:
                        self._save()

        workers = [threading.Thread(target=worker, daemon=True) for _ in range(min(self.connections, len(todo) or 1))]
        self.active = len(workers)
        for w in workers:
            w.start()
        for w in workers:
            w.join()
        self.active = 0
        self._save()
        if not self._stop.is_set() and len(self.done_chunks) < n:
            raise IOError(errors[-1] if errors else "Some parts could not be downloaded")

    def _fetch(self, f, start, end, already, holder):
        """Download bytes start..end into f; returns total bytes of this chunk written."""
        holder[0] = already
        req = urllib.request.Request(self.final_url, headers={"User-Agent": UA, "Range": f"bytes={start}-{end}"})
        with _opener().open(req, timeout=30) as r:
            if r.status != 206:
                raise IOError(f"Server ignored range request (HTTP {r.status})")
            f.seek(start)
            got = already
            want = end - start + 1
            while not self._stop.is_set():
                b = r.read(min(READ, want - (got - already)))
                if not b:
                    break
                f.write(b)
                got += len(b)
                holder[0] = got
                with self._lock:
                    self.bytes_done += len(b)
                if got - already >= want:
                    break
        if not self._stop.is_set() and got - already < want:
            raise IOError("Connection closed early")
        return got

    # ---------- reporting ----------
    def rate(self):
        now = time.time()
        t, b = self._last
        if now - t >= 0.9:
            inst = (self.bytes_done - b) / (now - t)
            self._rate = inst if self._rate == 0 else 0.5 * self._rate + 0.5 * inst
            self._last = (now, self.bytes_done)
        if self.status != "downloading":
            self._rate = 0.0
        return max(0.0, self._rate)

    def info(self):
        rate = self.rate()
        size = self.size or 0
        prog = 1.0 if self.status == "done" else (self.bytes_done / size if size else 0.0)
        kind = {"downloading": "down", "probing": "meta", "queued": "meta", "paused": "paused",
                "done": "done", "error": "error"}[self.status]
        return {
            "ih": self.id, "name": self.name, "progress": min(prog, 1.0), "down": rate, "up": 0,
            "peers": self.active, "seeds": 0, "size": size,
            "eta": int((size - self.bytes_done) / rate) if rate > 0 and size else -1,
            "state": -1, "http_state": self.status, "paused": self.status == "paused", "kind": kind,
            "seq": False, "error": self.error, "type": "http", "connections": self.connections,
            "ranges": self.ranges, "save_path": self.save_dir,
        }
