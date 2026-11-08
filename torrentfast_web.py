#!/usr/bin/env python3
"""
TorrentFast engine + local HTTP API, shared by the native app and the browser mode.

Browser mode:
  python torrentfast_web.py              -> http://localhost:8800
  python torrentfast_web.py --lan        -> also reachable from your phone on the same Wi-Fi
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

try:
    import libtorrent as lt
except ImportError:
    sys.exit("libtorrent is missing. Run:  pip install libtorrent")

from torrentfast import EXTRA_TRACKERS, make_session

APP_NAME = "TorrentFast"
LOCK = threading.RLock()


def resource(*parts):
    """Path to a bundled file (works from source and from a PyInstaller .exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def data_dir():
    if os.name == "nt":
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    else:
        d = os.path.join(os.path.expanduser("~"), ".config", "torrentfast")
    os.makedirs(os.path.join(d, "resume"), exist_ok=True)
    os.makedirs(os.path.join(d, "torrents"), exist_ok=True)
    return d


def default_save_dir():
    return os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME)


def open_path(path):
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 - opens Explorer on the user's own folder
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


class Engine:
    def __init__(self, args):
        self.args = args
        self.dir = data_dir()
        self.settings_file = os.path.join(self.dir, "settings.json")
        self.sources_file = os.path.join(self.dir, "sources.json")
        self.settings = {"lang": "auto", "save": default_save_dir()}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except (OSError, ValueError):
                pass
        if getattr(args, "out", None):
            self.settings["save"] = args.out
        os.makedirs(self.settings["save"], exist_ok=True)
        self.ses = make_session(args)
        self.sources = {}  # info_hash -> {"src": magnet or .torrent path, "save": folder}
        self.lan_url = None
        self._restore()
        threading.Thread(target=self._autosave, daemon=True).start()

    # ---------- persistence ----------
    def _write_json(self, path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def save_settings(self, **kw):
        self.settings.update({k: v for k, v in kw.items() if v is not None})
        os.makedirs(self.settings["save"], exist_ok=True)
        self._write_json(self.settings_file, self.settings)

    def _restore(self):
        if not os.path.exists(self.sources_file):
            return
        try:
            with open(self.sources_file, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return
        for entry in saved.values():
            try:
                self.add(entry["src"], save=entry.get("save"), persist=False)
            except Exception as e:  # keep going if one entry is broken
                print("Could not restore:", e)
        self._persist()

    def _persist(self):
        self._write_json(self.sources_file, self.sources)

    def _resume_path(self, ih):
        return os.path.join(self.dir, "resume", f"{ih}.fastresume")

    def _autosave(self):
        while True:
            time.sleep(60)
            self.save_resume()

    def save_resume(self):
        with LOCK:
            hs = [h for h in self.ses.get_torrents() if h.is_valid() and h.status().has_metadata]
            for h in hs:
                h.save_resume_data(lt.torrent_handle.save_info_dict)
        pending, deadline = len(hs), time.time() + 10
        while pending and time.time() < deadline:
            self.ses.wait_for_alert(500)
            for a in self.ses.pop_alerts():
                if isinstance(a, lt.save_resume_data_alert):
                    ih = str(a.handle.info_hashes().get_best())
                    with open(self._resume_path(ih), "wb") as f:
                        f.write(lt.write_resume_data_buf(a.params))
                    pending -= 1
                elif isinstance(a, lt.save_resume_data_failed_alert):
                    pending -= 1

    def shutdown(self):
        self.ses.pause()
        self.save_resume()

    # ---------- actions ----------
    def add(self, src, save=None, persist=True, torrent_bytes=None, filename=None):
        src = (src or "").strip()
        if torrent_bytes is not None:
            name = os.path.basename(filename or "upload.torrent")
            lt.torrent_info(lt.bdecode(torrent_bytes))  # validate before saving
            src = os.path.join(self.dir, "torrents", name)
            with open(src, "wb") as f:
                f.write(torrent_bytes)
        if src.startswith("magnet:"):
            p = lt.parse_magnet_uri(src)
        elif src.lower().endswith(".torrent") and os.path.isfile(src):
            p = lt.add_torrent_params()
            p.ti = lt.torrent_info(src)
        else:
            raise ValueError("Not a magnet link or .torrent file")
        ih = str(p.info_hashes.get_best())
        if ih in self.sources and self.find(ih):
            return ih  # already in the list
        save = save or self.settings["save"]
        rp = self._resume_path(ih)
        if os.path.exists(rp):
            with open(rp, "rb") as f:
                old = lt.read_resume_data(f.read())
            if p.ti is not None and old.ti is None:
                old.ti = p.ti
            p = old
        p.save_path = save
        p.trackers = list(p.trackers) + [t for t in EXTRA_TRACKERS if t not in p.trackers]
        with LOCK:
            self.ses.add_torrent(p)
            self.sources[ih] = {"src": src, "save": save}
            if persist:
                self._persist()
        return ih

    def find(self, ih):
        for h in self.ses.get_torrents():
            if str(h.info_hashes().get_best()) == ih:
                return h
        return None

    def action(self, ih, act):
        h = self.find(ih)
        if not h:
            raise ValueError("Torrent not found")
        with LOCK:
            if act == "pause":
                h.unset_flags(lt.torrent_flags.auto_managed)
                h.pause()
            elif act == "resume":
                h.set_flags(lt.torrent_flags.auto_managed)
                h.resume()
            elif act == "seq":
                if h.flags() & lt.torrent_flags.sequential_download:
                    h.unset_flags(lt.torrent_flags.sequential_download)
                else:
                    h.set_flags(lt.torrent_flags.sequential_download)
            elif act == "open":
                st = h.status()
                target = os.path.join(st.save_path, st.name) if st.name else st.save_path
                open_path(target if os.path.exists(target) else st.save_path)
            elif act in ("remove", "delete"):
                self.ses.remove_torrent(h, lt.session.delete_files if act == "delete" else 0)
                self.sources.pop(ih, None)
                self._persist()
                rp = self._resume_path(ih)
                if os.path.exists(rp):
                    os.remove(rp)
            else:
                raise ValueError("Unknown action")

    def bulk(self, act):
        for h in self.ses.get_torrents():
            self.action(str(h.info_hashes().get_best()), act)

    def status(self):
        items, down, up = [], 0, 0
        for h in self.ses.get_torrents():
            st = h.status()
            down += st.download_payload_rate
            up += st.upload_payload_rate
            paused = bool(st.flags & lt.torrent_flags.paused) and not bool(st.flags & lt.torrent_flags.auto_managed)
            if paused:
                kind = "paused"
            elif st.errc.value():
                kind = "error"
            elif st.state == lt.torrent_status.downloading_metadata:
                kind = "meta"
            elif st.is_seeding or st.state in (lt.torrent_status.finished, lt.torrent_status.seeding):
                kind = "done"
            elif st.state in (lt.torrent_status.checking_files, lt.torrent_status.checking_resume_data):
                kind = "check"
            else:
                kind = "down"
            rem = st.total_wanted - st.total_wanted_done
            items.append({
                "ih": str(h.info_hashes().get_best()),
                "name": st.name or "…",
                "progress": st.progress,
                "down": st.download_payload_rate,
                "up": st.upload_payload_rate,
                "peers": st.num_peers,
                "seeds": st.num_seeds,
                "size": st.total_wanted,
                "eta": int(rem / st.download_payload_rate) if st.download_payload_rate > 0 else -1,
                "state": int(st.state),
                "paused": paused,
                "kind": kind,
                "seq": bool(h.flags() & lt.torrent_flags.sequential_download),
                "error": st.errc.message() if st.errc.value() else "",
            })
        items.sort(key=lambda x: x["name"].lower())
        return {"items": items, "down": down, "up": up, "out": self.settings["save"],
                "port": self.ses.listen_port()}

    # ---------- Windows file associations ----------
    def associate(self):
        if os.name != "nt":
            raise ValueError("Only available on Windows")
        import winreg
        exe = sys.executable if getattr(sys, "frozen", False) else f'{sys.executable}" "{os.path.abspath(sys.argv[0])}'
        cmd = f'"{exe}" "%1"'
        base = r"Software\Classes"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\magnet") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Magnet Link")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\magnet\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{sys.executable}",0')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\magnet\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\.torrent") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "TorrentFast.torrent")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\TorrentFast.torrent\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        self.save_settings(associated=True)


def make_handler(engine):
    page_path = resource("ui", "index.html")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                with open(page_path, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._json(engine.status())
            elif path == "/api/settings":
                s = dict(engine.settings)
                s.update(lan_url=engine.lan_url, lan_active=bool(engine.lan_url), can_associate=os.name == "nt",
                         associated=bool(s.get("associated")))
                self._json(s)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20 * 1024 * 1024:
                return self._json({"error": "too large"}, 413)
            body = self.rfile.read(n) if n else b""
            try:
                data = json.loads(body) if body and u.path != "/api/upload" else {}
                if u.path == "/api/add":
                    self._json({"ih": engine.add(data.get("src"))})
                elif u.path == "/api/upload":
                    name = parse_qs(u.query).get("name", ["upload.torrent"])[0]
                    self._json({"ih": engine.add("", torrent_bytes=body, filename=name)})
                elif u.path == "/api/action":
                    engine.action(data["ih"], data["act"])
                    self._json({"ok": True})
                elif u.path == "/api/bulk":
                    engine.bulk(data["act"])
                    self._json({"ok": True})
                elif u.path == "/api/open_folder":
                    open_path(engine.settings["save"])
                    self._json({"ok": True})
                elif u.path == "/api/settings":
                    engine.save_settings(lang=data.get("lang"), save=data.get("save"), lan=data.get("lan"))
                    self._json({"ok": True})
                elif u.path == "/api/associate":
                    engine.associate()
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, 404)
            except Exception as e:
                self._json({"error": str(e)}, 400)

    return Handler


def start_server(engine, host="127.0.0.1", port=8800):
    """Start the API in a background thread. Falls back to a free port if taken."""
    try:
        srv = ThreadingHTTPServer((host, port), make_handler(engine))
    except OSError:
        srv = ThreadingHTTPServer((host, 0), make_handler(engine))
    port = srv.server_address[1]
    if host == "0.0.0.0":
        ip = lan_ip()
        engine.lan_url = f"http://{ip}:{port}" if ip else None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def add_common_args(ap):
    ap.add_argument("-o", "--out", help="download folder")
    ap.add_argument("--port", type=int, default=6881, help="P2P listen port")
    ap.add_argument("--web-port", type=int, default=8800)
    ap.add_argument("--lan", action="store_true", help="allow access from other devices on your network")
    ap.add_argument("--max-down", type=int, default=0, help="KB/s, 0 = unlimited")
    ap.add_argument("--max-up", type=int, default=0, help="KB/s, 0 = unlimited")


def main():
    ap = argparse.ArgumentParser(description="TorrentFast (browser mode)")
    add_common_args(ap)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    engine = Engine(args)
    _, port = start_server(engine, "0.0.0.0" if (args.lan or engine.settings.get("lan")) else "127.0.0.1", args.web_port)
    url = f"http://localhost:{port}"
    print(f"TorrentFast running at {url}" + (f"  (phone: {engine.lan_url})" if engine.lan_url else ""))
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSaving progress…")
        engine.shutdown()


if __name__ == "__main__":
    main()
