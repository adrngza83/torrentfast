#!/usr/bin/env python3
"""
TorrentFast desktop app: native window (Edge WebView2 on Windows) around the TorrentFast engine.

  TorrentFast.exe                       open the app
  TorrentFast.exe "magnet:?xt=..."      add a magnet (to the running window if already open)
  TorrentFast.exe file.torrent          add a .torrent file
  TorrentFast.exe --lan                 also allow access from your phone
  TorrentFast.exe --selftest            start the engine without a window, check the API and exit (CI)
"""
import argparse
import json
import logging
import os
import sys
import time
import traceback
import urllib.parse
import urllib.request

from torrentfast_web import APP_NAME, Engine, add_common_args, data_dir, start_server

PORT_FILE = os.path.join(data_dir(), "instance.json")
logging.basicConfig(filename=os.path.join(data_dir(), "app.log"), level=logging.INFO,
                    format="%(asctime)s [%(process)d] %(levelname)s %(message)s")
log = logging.getLogger("torrentfast")

# Talk to our own local server directly, never through a system proxy.
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def running_instance():
    """Return the port of an already-open TorrentFast window, or None."""
    try:
        with open(PORT_FILE, encoding="utf-8") as f:
            port = json.load(f)["port"]
    except Exception:
        return None
    for _ in range(3):  # the open window may be busy for a moment
        try:
            LOCAL.open(f"http://127.0.0.1:{port}/api/status", timeout=3).read()
            return port
        except Exception as e:
            log.warning("instance on port %s not answering: %s", port, e)
            time.sleep(0.5)
    return None


def send_to_instance(port, items):
    for item in items:
        if item.lower().endswith(".torrent") and os.path.isfile(item):
            with open(item, "rb") as f:
                data = f.read()
            url = f"http://127.0.0.1:{port}/api/upload?name={urllib.parse.quote(os.path.basename(item))}"
        else:
            data = json.dumps({"src": item}).encode()
            url = f"http://127.0.0.1:{port}/api/add"
        req = urllib.request.Request(url, data=data, method="POST")
        try:
            LOCAL.open(req, timeout=10).read()
            log.info("handed %s to running instance", item[:60])
        except Exception as e:
            log.error("could not hand off %s: %s", item[:60], e)


class JsApi:
    """Functions the page can call through window.pywebview.api."""

    def __init__(self):
        self._window = None  # underscore: pywebview must not expose/inspect it

    def choose_folder(self):
        import webview
        res = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return res[0] if res else None


def main():
    ap = argparse.ArgumentParser(description="TorrentFast")
    add_common_args(ap)
    ap.add_argument("items", nargs="*", help="magnet links or .torrent files to add")
    ap.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    log.info("start args=%s", [a[:60] for a in sys.argv[1:]])
    if not args.selftest:
        port = running_instance()
        if port:
            send_to_instance(port, args.items)
            log.info("exit after hand-off")
            os._exit(0)

    engine = Engine(args)
    _, port = start_server(engine, "0.0.0.0" if (args.lan or engine.settings.get("lan")) else "127.0.0.1", args.web_port)
    for item in args.items:
        try:
            if item.lower().endswith(".torrent") and os.path.isfile(item):
                with open(item, "rb") as f:
                    engine.add("", torrent_bytes=f.read(), filename=os.path.basename(item))
            else:
                engine.add(item)
        except Exception as e:
            print("Could not add:", e)

    if args.selftest:
        try:
            body = LOCAL.open(f"http://127.0.0.1:{port}/api/status", timeout=5).read()
            page = LOCAL.open(f"http://127.0.0.1:{port}/", timeout=5).read()
            ok = b"TorrentFast" in page and "items" in json.loads(body)
            import webview  # noqa: F401  (make sure the GUI toolkit is bundled)
        except Exception as e:
            ok = False
            print("SELFTEST FAILED:", e)
        print("SELFTEST OK" if ok else "SELFTEST FAILED")
        engine.shutdown()
        os._exit(0 if ok else 1)

    with open(PORT_FILE, "w", encoding="utf-8") as f:
        json.dump({"port": port, "pid": os.getpid()}, f)
    log.info("window starting, api on port %s", port)

    import webview

    api = JsApi()
    window = webview.create_window(
        APP_NAME, f"http://127.0.0.1:{port}/", js_api=api,
        width=1180, height=760, min_size=(760, 480), background_color="#202020",
        text_select=False,
    )
    api._window = window
    try:
        webview.start(private_mode=False, storage_path=os.path.join(data_dir(), "webview"))
    finally:
        try:
            os.remove(PORT_FILE)
        except OSError:
            pass
        engine.shutdown()
    time.sleep(0.2)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log.error("crash:\n%s", traceback.format_exc())
        os._exit(1)
