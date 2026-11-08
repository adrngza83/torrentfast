<p align="center"><img src="assets/icon.png" width="96" alt="TorrentFast icon"></p>

<h1 align="center">TorrentFast</h1>

<p align="center">
A fast, native-looking torrent downloader for Windows.<br>
Created by <b>Adrián Garza Garza</b> (<a href="https://github.com/adrngza83">@adrngza83</a>)
</p>

<p align="center">
<a href="https://github.com/adrngza83/torrentfast/actions/workflows/build-exe.yml"><img src="https://github.com/adrngza83/torrentfast/actions/workflows/build-exe.yml/badge.svg" alt="Build"></a>
<a href="https://github.com/adrngza83/torrentfast/releases/latest"><img src="https://img.shields.io/github/v/release/adrngza83/torrentfast" alt="Latest release"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
<img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6" alt="Windows 10 | 11">
</p>

<p align="center"><b>English</b> · <a href="README.es.md">Español</a></p>

---

## Download

1. Go to [**Releases**](https://github.com/adrngza83/torrentfast/releases/latest) and download **`TorrentFast.exe`**.
2. Double-click it. No installation needed.

> **First run:** Windows SmartScreen may say *"Windows protected your PC"* because the app isn't code-signed yet. Click **More info → Run anyway**. When the firewall asks, allow **private networks** so more peers can reach you.

## Features

- 🪟 **Native Windows 11 look**: its own window, light/dark theme that follows Windows, Fluent icons
- 🎨 **Color-coded status**: 🔵 downloading · 🟡 fetching metadata · 🟢 completed · ⚪ paused · 🔴 error
- 🎯 **Focus mode** hides finished and paused items
- 📋 **Paste a magnet with Ctrl+V** anywhere in the window, or **drag & drop `.torrent` files**
- 🧲 **Open magnet links with TorrentFast**: one click in Settings and every magnet you click in your browser goes straight to the app
- ▶️ **Sequential download** to watch a video while it downloads
- ⏯ Pause/resume everything; downloads continue where they left off after a restart
- 📱 **Phone access** (optional): control it from any device on your Wi-Fi
- ⚡ **Segmented direct downloads**: paste any `https://` link and it downloads with up to 32 parallel connections, like IDM or aria2
- 🪞 **Mirror servers**: add a direct link to a torrent and download from that server and from peers at the same time
- 🧠 **Smart priority**: the best-seeded torrents go first, plus a *Download this first* button
- 🚀 **Full download speed, capped upload**: set your internet speed (default 300 Mbps) and upload is limited to a share of it (default 10%); download is never limited
- 🌐 Spanish and English, automatic by system language

## Why it's fast

Built on [libtorrent](https://libtorrent.org) (the engine behind qBittorrent and Deluge), tuned aggressively:

- Up to 2,000 connections, 200 new connections per second
- Deep request queues per peer
- DHT, local peer discovery and 10 extra public trackers to find peers quickly
- Automatic router port mapping (UPnP / NAT-PMP)
- Protocol encryption to avoid ISP throttling

**Tip:** if UPnP doesn't work on your router, forward port **6881 (TCP and UDP)** manually. It's the single biggest speed boost.

## Command-line version

```
TorrentFast-CLI.exe "magnet:?xt=urn:btih:..."
TorrentFast-CLI.exe file.torrent -o D:\Downloads --seq
TorrentFast-CLI.exe list.txt --seed 1.5 --max-down 5000
```

## Run from source

```
pip install -r requirements.txt
python torrentfast_app.py      # desktop app
python torrentfast_web.py      # browser mode (http://localhost:8800)
python torrentfast.py MAGNET   # command line
```

| File | What it does |
|---|---|
| `torrentfast.py` | Tuned libtorrent session and the command-line downloader |
| `torrentfast_http.py` | Segmented HTTP downloader (parallel ranges, resume) |
| `torrentfast_web.py` | Engine (queue, resume, settings) and local HTTP API |
| `torrentfast_app.py` | Native window (Edge WebView2), single instance, magnet hand-off |
| `ui/index.html` | The interface (Fluent design, ES/EN) |

Run the tests with `python -m pytest`. Every push is tested and built on Windows by GitHub Actions; publishing a release attaches the `.exe` files automatically.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md). Release notes: [CHANGELOG.md](CHANGELOG.md).

## Responsible use

Use TorrentFast for content you have the right to download: Linux distributions, open-licensed media, public-domain works and your own files.

## License

[MIT](LICENSE) © 2026 Adrián Garza Garza
