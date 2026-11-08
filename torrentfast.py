#!/usr/bin/env python3
"""
TorrentFast — descargador de torrents rápido por línea de comandos.
Motor: libtorrent (el mismo de qBittorrent/Deluge), afinado para velocidad.

Uso:
  python torrentfast.py "magnet:?xt=urn:btih:..."
  python torrentfast.py archivo.torrent -o D:/Descargas
  python torrentfast.py lista.txt          (un magnet o .torrent por línea)
  python torrentfast.py MAGNET --seq       (descarga secuencial, para ver video mientras baja)
  python torrentfast.py MAGNET --seed 2.0  (sigue sembrando hasta ratio 2.0)
  python torrentfast.py MAGNET --max-down 5000  (límite en KB/s)

Ctrl+C pausa y guarda el avance; vuelve a correr el mismo comando para reanudar.
"""
import argparse
import os
import sys
import time

try:
    import libtorrent as lt
except ImportError:
    sys.exit("Falta libtorrent. Instálalo con:  pip install libtorrent")

# Trackers públicos extra: más fuentes de peers = arranque más rápido
EXTRA_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://explodie.org:6969/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://tracker1.bt.moack.co.kr:80/announce",
]

STATES = ["en cola", "verificando", "bajando metadatos", "descargando",
          "terminado", "sembrando", "asignando", "revisando resume"]

# Colores ANSI (funcionan en Windows Terminal, PowerShell moderno, macOS, Linux)
C = {"g": "\033[92m", "y": "\033[93m", "c": "\033[96m", "r": "\033[91m",
     "b": "\033[1m", "d": "\033[2m", "x": "\033[0m"}
if os.name == "nt":
    os.system("")  # habilita ANSI en consolas de Windows


def human(n):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:6.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def eta(remaining, rate):
    if rate <= 0:
        return "--:--:--"
    s = int(remaining / rate)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def make_session(args):
    s = {
        "user_agent": "TorrentFast/1.0 libtorrent/" + lt.__version__,
        "listen_interfaces": f"0.0.0.0:{args.port},[::]:{args.port}",
        # Descubrimiento de peers
        "enable_dht": True, "enable_lsd": True,
        "enable_upnp": True, "enable_natpmp": True,
        "dht_bootstrap_nodes": "dht.libtorrent.org:25401,router.bittorrent.com:6881,"
                               "router.utorrent.com:6881,dht.transmissionbt.com:6881",
        # Más conexiones y más rápidas
        "connections_limit": 2000,
        "connection_speed": 200,          # conexiones nuevas por segundo
        "unchoke_slots_limit": 64,
        "max_out_request_queue": 1500,
        "max_allowed_in_request_queue": 2000,
        "request_queue_time": 5,
        "whole_pieces_threshold": 20,
        "peer_timeout": 60,
        "inactivity_timeout": 300,
        "mixed_mode_algorithm": 0,        # prefiere TCP
        "torrent_connect_boost": 50,
        # Disco
        "aio_threads": 8,
        "send_buffer_watermark": 5 * 1024 * 1024,
        "send_buffer_watermark_factor": 150,
        # Trackers: anunciar a todos a la vez
        "announce_to_all_trackers": True,
        "announce_to_all_tiers": True,
        # Cifrado opcional (ayuda con ISPs que estrangulan BitTorrent)
        "out_enc_policy": lt.enc_policy.enabled,
        "in_enc_policy": lt.enc_policy.enabled,
        "allowed_enc_level": lt.enc_level.both,
        "alert_mask": lt.alert.category_t.error_notification
                      | lt.alert.category_t.status_notification
                      | lt.alert.category_t.storage_notification,
        "active_downloads": 8, "active_seeds": 8, "active_limit": 20,
    }
    if args.max_down:
        s["download_rate_limit"] = args.max_down * 1024
    if args.max_up:
        s["upload_rate_limit"] = args.max_up * 1024
    return lt.session(s)


def resume_path(save, info_hash):
    d = os.path.join(save, ".torrentfast")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{info_hash}.fastresume")


def build_params(source, save):
    source = source.strip()
    if source.startswith("magnet:"):
        p = lt.parse_magnet_uri(source)
    elif os.path.isfile(source):
        p = lt.add_torrent_params()
        p.ti = lt.torrent_info(source)
    else:
        raise ValueError(f"No reconozco esta fuente: {source[:80]}")

    ih = str(p.info_hashes.get_best() if hasattr(p, "info_hashes") else p.info_hash)
    rp = resume_path(save, ih)
    if os.path.exists(rp):  # reanudar donde se quedó
        with open(rp, "rb") as f:
            old = lt.read_resume_data(f.read())
        if p.ti is not None and old.ti is None:
            old.ti = p.ti
        p = old
        print(f"{C['c']}↻ Reanudando {ih[:12]}…{C['x']}")
    p.save_path = save
    p.trackers = list(p.trackers) + [t for t in EXTRA_TRACKERS if t not in p.trackers]
    return p


def save_all_resume(ses, handles, save):
    pending = 0
    for h in handles:
        if h.is_valid() and h.status().has_metadata:
            h.save_resume_data(lt.torrent_handle.save_info_dict)
            pending += 1
    deadline = time.time() + 10
    while pending and time.time() < deadline:
        ses.wait_for_alert(1000)
        for a in ses.pop_alerts():
            if isinstance(a, lt.save_resume_data_alert):
                ih = str(a.handle.info_hashes().get_best())
                with open(resume_path(save, ih), "wb") as f:
                    f.write(lt.write_resume_data_buf(a.params))
                pending -= 1
            elif isinstance(a, lt.save_resume_data_failed_alert):
                pending -= 1


def bar(frac, width=28):
    full = int(frac * width)
    return "█" * full + "░" * (width - full)


def main():
    ap = argparse.ArgumentParser(description="TorrentFast — descargas de torrents rápidas")
    ap.add_argument("sources", nargs="+", help="magnet, archivo .torrent o .txt con una lista")
    ap.add_argument("-o", "--out", default=os.path.join(os.path.expanduser("~"), "Downloads", "TorrentFast"),
                    help="carpeta de destino")
    ap.add_argument("--port", type=int, default=6881, help="puerto de escucha (ábrelo en tu router para más velocidad)")
    ap.add_argument("--seq", action="store_true", help="descarga secuencial (streaming)")
    ap.add_argument("--seed", type=float, default=0.0, help="seguir sembrando hasta este ratio (0 = salir al terminar)")
    ap.add_argument("--max-down", type=int, default=0, help="límite de bajada en KB/s (0 = sin límite)")
    ap.add_argument("--max-up", type=int, default=0, help="límite de subida en KB/s (0 = sin límite)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Expandir listas .txt
    sources = []
    for s in args.sources:
        if s.lower().endswith(".txt") and os.path.isfile(s):
            with open(s, encoding="utf-8") as f:
                sources += [l.strip() for l in f if l.strip() and not l.startswith("#")]
        else:
            sources.append(s)

    ses = make_session(args)
    handles = []
    for src in sources:
        try:
            p = build_params(src, args.out)
            h = ses.add_torrent(p)
            if args.seq:
                h.set_flags(lt.torrent_flags.sequential_download)
            handles.append(h)
        except Exception as e:
            print(f"{C['r']}✗ {e}{C['x']}")
    if not handles:
        sys.exit("Nada que descargar.")

    print(f"{C['b']}TorrentFast{C['x']} · libtorrent {lt.__version__} · destino: {args.out}")
    print(f"{C['d']}Ctrl+C para pausar y guardar avance{C['x']}\n")

    last_lines = 0
    try:
        while True:
            for a in ses.pop_alerts():
                if isinstance(a, lt.torrent_error_alert) or isinstance(a, lt.file_error_alert):
                    print(f"{C['r']}! {a.message()}{C['x']}")

            lines = []
            all_done = True
            tot_down = tot_up = 0
            for h in handles:
                st = h.status()
                tot_down += st.download_payload_rate
                tot_up += st.upload_payload_rate
                name = (st.name or "obteniendo metadatos…")[:40]
                state = STATES[st.state] if st.state < len(STATES) else str(st.state)
                done = st.is_seeding or st.state in (lt.torrent_status.finished, lt.torrent_status.seeding)
                ratio = st.all_time_upload / max(st.total_wanted, 1)
                if not done or (args.seed and ratio < args.seed):
                    all_done = False
                col = C["g"] if done else (C["y"] if st.state == lt.torrent_status.downloading_metadata else C["c"])
                lines.append(
                    f"{col}{bar(st.progress)}{C['x']} {st.progress * 100:5.1f}%  "
                    f"↓{human(st.download_payload_rate)}/s ↑{human(st.upload_payload_rate)}/s  "
                    f"peers {st.num_peers:3d} ({st.num_seeds} seeds)  "
                    f"ETA {eta(st.total_wanted - st.total_wanted_done, st.download_payload_rate)}  "
                    f"{C['d']}{state}{C['x']}  {name}"
                )
            lines.append(f"{C['b']}Total ↓{human(tot_down)}/s  ↑{human(tot_up)}/s{C['x']}")

            if last_lines:
                sys.stdout.write(f"\033[{last_lines}F")
            sys.stdout.write("\n".join(l + "\033[K" for l in lines) + "\n")
            sys.stdout.flush()
            last_lines = len(lines)

            if all_done:
                print(f"\n{C['g']}✓ Todo listo en {args.out}{C['x']}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{C['y']}⏸ Pausando y guardando avance…{C['x']}")
    finally:
        ses.pause()
        save_all_resume(ses, handles, args.out)


if __name__ == "__main__":
    main()
