#!/usr/bin/env python3
"""
TorrentFast Web — interfaz web con colores para TorrentFast.
Abre http://localhost:8800 (o http://IP-de-tu-PC:8800 desde el celular en tu WiFi).

  python torrentfast_web.py                 (descarga en ~/Downloads/TorrentFast)
  python torrentfast_web.py -o D:/Descargas --web-port 8800
"""
import argparse
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import libtorrent as lt
except ImportError:
    sys.exit("Falta libtorrent. Corre instalar.bat o:  pip install libtorrent")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from torrentfast import EXTRA_TRACKERS, STATES, make_session, resume_path  # noqa: E402

LOCK = threading.Lock()


class Engine:
    def __init__(self, args):
        self.args = args
        self.save = args.out
        os.makedirs(self.save, exist_ok=True)
        self.ses = make_session(args)
        self.sources_file = os.path.join(self.save, ".torrentfast", "sources.json")
        os.makedirs(os.path.dirname(self.sources_file), exist_ok=True)
        self.sources = {}  # info_hash -> magnet o ruta .torrent
        self._restore()
        threading.Thread(target=self._autosave, daemon=True).start()

    # ---------- persistencia ----------
    def _restore(self):
        if os.path.exists(self.sources_file):
            try:
                with open(self.sources_file, encoding="utf-8") as f:
                    saved = json.load(f)
                for src in saved.values():
                    try:
                        self.add(src, persist=False)
                    except Exception as e:
                        print("No se pudo restaurar:", e)
            except Exception:
                pass

    def _persist(self):
        with open(self.sources_file, "w", encoding="utf-8") as f:
            json.dump(self.sources, f)

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
                    with open(resume_path(self.save, ih), "wb") as f:
                        f.write(lt.write_resume_data_buf(a.params))
                    pending -= 1
                elif isinstance(a, lt.save_resume_data_failed_alert):
                    pending -= 1

    # ---------- acciones ----------
    def add(self, src, persist=True, torrent_bytes=None, filename=None):
        src = (src or "").strip()
        if torrent_bytes is not None:
            tdir = os.path.join(self.save, ".torrentfast", "torrents")
            os.makedirs(tdir, exist_ok=True)
            path = os.path.join(tdir, os.path.basename(filename or "subido.torrent"))
            with open(path, "wb") as f:
                f.write(torrent_bytes)
            src = path
        if src.startswith("magnet:"):
            p = lt.parse_magnet_uri(src)
        elif os.path.isfile(src):
            p = lt.add_torrent_params()
            p.ti = lt.torrent_info(src)
        else:
            raise ValueError("Pega un enlace magnet o sube un archivo .torrent")
        ih = str(p.info_hashes.get_best())
        rp = resume_path(self.save, ih)
        if os.path.exists(rp):
            with open(rp, "rb") as f:
                old = lt.read_resume_data(f.read())
            if p.ti is not None and old.ti is None:
                old.ti = p.ti
            p = old
        p.save_path = self.save
        p.trackers = list(p.trackers) + [t for t in EXTRA_TRACKERS if t not in p.trackers]
        with LOCK:
            self.ses.add_torrent(p)
            self.sources[ih] = src
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
            raise ValueError("No existe ese torrent")
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
            elif act in ("remove", "delete"):
                opt = lt.session.delete_files if act == "delete" else 0
                self.ses.remove_torrent(h, opt)
                self.sources.pop(ih, None)
                self._persist()
                rp = resume_path(self.save, ih)
                if os.path.exists(rp):
                    os.remove(rp)
            else:
                raise ValueError("Acción desconocida")

    def status(self):
        items, down, up = [], 0, 0
        for h in self.ses.get_torrents():
            st = h.status()
            down += st.download_payload_rate
            up += st.upload_payload_rate
            paused = bool(st.flags & lt.torrent_flags.paused)
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
                "name": st.name or "Obteniendo metadatos…",
                "progress": st.progress,
                "down": st.download_payload_rate,
                "up": st.upload_payload_rate,
                "peers": st.num_peers,
                "seeds": st.num_seeds,
                "size": st.total_wanted,
                "done": st.total_wanted_done,
                "eta": int(rem / st.download_payload_rate) if st.download_payload_rate > 0 else -1,
                "state": "pausado" if paused else (STATES[st.state] if st.state < len(STATES) else "?"),
                "kind": kind,
                "seq": bool(h.flags() & lt.torrent_flags.sequential_download),
                "error": st.errc.message() if st.errc.value() else "",
            })
        items.sort(key=lambda x: x["name"].lower())
        return {"items": items, "down": down, "up": up, "out": self.save,
                "port": self.ses.listen_port()}


PAGE = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TorrentFast</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--line:#262a33;--tx:#e8eaf0;--mut:#8a90a0;
--down:#38bdf8;--done:#22c55e;--meta:#facc15;--paused:#94a3b8;--error:#ef4444;--check:#a78bfa}
*{box-sizing:border-box}body{margin:0;font:15px/1.4 system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:2}
h1{margin:0;font-size:20px}h1 b{color:var(--down)}
.tot{display:flex;gap:16px;font-variant-numeric:tabular-nums}.tot span{font-weight:600}
.dn{color:var(--down)}.upc{color:var(--done)}
main{max-width:1000px;margin:0 auto;padding:16px}
form{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
input[type=text]{flex:1;min-width:220px;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--tx);font-size:15px}
button,.filebtn{padding:11px 16px;border-radius:10px;border:0;font-weight:600;cursor:pointer;background:var(--down);color:#00131d;font-size:14px}
.filebtn{background:var(--card);color:var(--tx);border:1px solid var(--line)}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}
.chip{padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--mut);font-weight:500}
.chip.on{color:var(--tx);border-color:var(--tx)}
.chip i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.t{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--c);border-radius:12px;padding:12px 14px;margin-bottom:10px}
.row{display:flex;justify-content:space-between;gap:10px;align-items:center}
.name{font-weight:600;word-break:break-all}
.badge{font-size:12px;padding:2px 8px;border-radius:999px;background:color-mix(in srgb,var(--c) 18%,transparent);color:var(--c);white-space:nowrap}
.bar{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin:10px 0 8px}
.bar div{height:100%;background:var(--c);transition:width .6s}
.meta{display:flex;flex-wrap:wrap;gap:14px;color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums}
.meta b{color:var(--tx);font-weight:600}
.acts{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.acts button{background:transparent;color:var(--mut);border:1px solid var(--line);padding:6px 10px;font-weight:500}
.acts button:hover{color:var(--tx);border-color:var(--tx)}
.acts .del:hover{color:var(--error);border-color:var(--error)}
.acts .on{color:var(--down);border-color:var(--down)}
.empty{color:var(--mut);text-align:center;padding:40px}
.foot{color:var(--mut);font-size:12px;margin-top:16px}
#msg{min-height:20px;font-size:13px;margin-bottom:6px}
body.focus .t:not([data-k=down]):not([data-k=meta]){display:none}
</style></head><body>
<header><h1>Torrent<b>Fast</b></h1>
<div class="tot"><div>↓ <span class="dn" id="td">0</span></div><div>↑ <span class="upc" id="tu">0</span></div></div></header>
<main>
<form id="f"><input type="text" id="mag" placeholder="Pega un enlace magnet:?xt=…" autocomplete="off">
<button>Descargar</button>
<label class="filebtn">.torrent<input type="file" id="file" accept=".torrent" multiple hidden></label></form>
<div id="msg"></div>
<div class="filters" id="fl"></div>
<div id="list"></div>
<div class="foot" id="foot"></div>
</main>
<script>
const COL={down:'var(--down)',done:'var(--done)',meta:'var(--meta)',paused:'var(--paused)',error:'var(--error)',check:'var(--check)'};
const LBL={all:'Todos',down:'Descargando',meta:'Buscando',done:'Listos',paused:'Pausados',error:'Error',focus:'Modo enfoque'};
let filt='all',focus=false;
const h=n=>{const u=['B','KB','MB','GB','TB'];let i=0;while(n>=1024&&i<4){n/=1024;i++}return n.toFixed(i?1:0)+' '+u[i]};
const eta=s=>s<0?'—':`${Math.floor(s/3600)}h ${String(Math.floor(s%3600/60)).padStart(2,'0')}m`;
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function msg(t,ok){const m=document.getElementById('msg');m.textContent=t;m.style.color=ok?'var(--done)':'var(--error)';setTimeout(()=>m.textContent='',4000)}
async function api(p,b){const r=await fetch(p,{method:'POST',body:b});const j=await r.json();if(!r.ok)throw new Error(j.error);return j}
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const v=mag.value.trim();if(!v)return;
 try{await api('/api/add',JSON.stringify({src:v}));mag.value='';msg('Agregado ✓',1);tick()}catch(x){msg(x.message)}};
file.onchange=async()=>{for(const f of file.files){try{await fetch('/api/upload?name='+encodeURIComponent(f.name),{method:'POST',body:f}).then(async r=>{if(!r.ok)throw new Error((await r.json()).error)});msg('Agregado ✓',1)}catch(x){msg(x.message)}}file.value='';tick()};
async function act(ih,a){if(a==='delete'&&!confirmDel(ih))return;try{await api('/api/action',JSON.stringify({ih,act:a}));tick()}catch(x){msg(x.message)}}
const armed={};function confirmDel(ih){if(armed[ih]){delete armed[ih];return true}armed[ih]=1;msg('Toca "Borrar archivos" otra vez para confirmar');setTimeout(()=>delete armed[ih],4000);return false}
function filters(items){const c={all:items.length};items.forEach(t=>c[t.kind]=(c[t.kind]||0)+1);
 fl.innerHTML=['all','down','meta','done','paused','error'].filter(k=>k==='all'||c[k]).map(k=>`<button class="chip ${filt===k?'on':''}" onclick="filt='${k}';tick()">${k!=='all'?`<i style="background:${COL[k]}"></i>`:''}${LBL[k]} ${c[k]||0}</button>`).join('')+
 `<button class="chip ${focus?'on':''}" onclick="focus=!focus;document.body.classList.toggle('focus',focus);tick()">◎ ${LBL.focus}</button>`}
async function tick(){try{const d=await (await fetch('/api/status')).json();
 td.textContent=h(d.down)+'/s';tu.textContent=h(d.up)+'/s';document.title=`↓${h(d.down)}/s · TorrentFast`;
 filters(d.items);const it=d.items.filter(t=>filt==='all'||t.kind===filt);
 list.innerHTML=it.length?it.map(t=>`<div class="t" data-k="${t.kind}" style="--c:${COL[t.kind]}">
 <div class="row"><div class="name">${esc(t.name)}</div><span class="badge">${t.state}</span></div>
 <div class="bar"><div style="width:${(t.progress*100).toFixed(1)}%"></div></div>
 <div class="meta"><span><b>${(t.progress*100).toFixed(1)}%</b> de ${h(t.size)}</span><span>↓ <b>${h(t.down)}/s</b></span><span>↑ ${h(t.up)}/s</span>
 <span>peers <b>${t.peers}</b> (${t.seeds} seeds)</span><span>ETA <b>${eta(t.eta)}</b></span>${t.error?`<span style="color:var(--error)">${esc(t.error)}</span>`:''}</div>
 <div class="acts">${t.kind==='paused'?`<button onclick="act('${t.ih}','resume')">▶ Reanudar</button>`:`<button onclick="act('${t.ih}','pause')">⏸ Pausar</button>`}
 <button class="${t.seq?'on':''}" onclick="act('${t.ih}','seq')">▤ Secuencial</button>
 <button onclick="act('${t.ih}','remove')">Quitar</button><button class="del" onclick="act('${t.ih}','delete')">🗑 Borrar archivos</button></div></div>`).join('')
 :'<div class="empty">Nada por aquí. Pega un magnet arriba.</div>';
 foot.textContent=`Guardando en ${d.out} · puerto P2P ${d.port}`}catch(e){foot.textContent='Sin conexión con TorrentFast…'}}
tick();setInterval(tick,1000);
</script></body></html>"""


def make_handler(engine):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                b = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            elif path == "/api/status":
                self._json(engine.status())
            else:
                self._json({"error": "no encontrado"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            try:
                if u.path == "/api/add":
                    self._json({"ih": engine.add(json.loads(body)["src"])})
                elif u.path == "/api/upload":
                    from urllib.parse import parse_qs
                    name = parse_qs(u.query).get("name", ["subido.torrent"])[0]
                    self._json({"ih": engine.add("", torrent_bytes=body, filename=name)})
                elif u.path == "/api/action":
                    d = json.loads(body)
                    engine.action(d["ih"], d["act"])
                    self._json({"ok": True})
                else:
                    self._json({"error": "no encontrado"}, 404)
            except Exception as e:
                self._json({"error": str(e)}, 400)
    return H


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "IP-de-tu-PC"


def main():
    ap = argparse.ArgumentParser(description="TorrentFast Web")
    ap.add_argument("-o", "--out", default=os.path.join(os.path.expanduser("~"), "Downloads", "TorrentFast"))
    ap.add_argument("--port", type=int, default=6881, help="puerto P2P")
    ap.add_argument("--web-port", type=int, default=8800)
    ap.add_argument("--max-down", type=int, default=0)
    ap.add_argument("--max-up", type=int, default=0)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    engine = Engine(args)
    srv = ThreadingHTTPServer(("0.0.0.0", args.web_port), make_handler(engine))
    url = f"http://localhost:{args.web_port}"
    print(f"TorrentFast Web listo:\n  En esta PC:  {url}\n  En tu cel:   http://{lan_ip()}:{args.web_port}  (misma WiFi)")
    print(f"  Descargas en: {args.out}\nCtrl+C para cerrar (guarda el avance).")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nGuardando avance…")
        engine.ses.pause()
        engine.save_resume()


if __name__ == "__main__":
    main()
