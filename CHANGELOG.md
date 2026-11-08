# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-11-07
### Added
- **Segmented direct downloads** (IDM / aria2 style): paste any `https://` link and it downloads with up to 32 parallel connections (16 by default), pause/resume and resume after restart. Servers without range support fall back to one connection.
- **Mirror servers (web seeds)** for torrents: add a direct link for the same file and TorrentFast downloads from that server and from peers at the same time. Mirrors already inside a torrent or magnet (`ws=`) are used automatically, with more connections.
- **Smart priority**: torrents with the most people sharing move to the front of the queue; stalled torrents no longer block a download slot.
- **Download this first** button per torrent; your choice always beats smart priority.
- Links to `.torrent` files can be pasted directly.
- Automated tests (`pytest`) run on Windows on every change.

### Fixed
- Deleting an unfinished direct download can never remove another file with the same name.

## [1.2.0] - 2026-11-07
### Added
- Upload cap based on your line speed: set your internet speed (default 300 Mbps) and the share for uploading (default 10% = 30 Mbps). Download is never limited.
- Status bar shows speeds in Mb/s next to your line speed and the upload limit.
- CLI: `--line-mbps` and `--up-pct`.

### Changed
- High-bandwidth tuning for 300 Mbps+ connections: 64 MB disk queue, larger socket buffers, 4 hashing threads, protocol overhead no longer counted against limits.

### Fixed
- CI launch test could hang; it now has timeouts and the app retries when handing a magnet to an already-open window.

## [1.1.0] - 2026-11-07
### Added
- Native desktop app (`TorrentFast.exe`): its own window with a Windows 11 Fluent design, light/dark theme and app icon.
- Drag & drop `.torrent` files and paste magnets with Ctrl+V.
- Optional "open magnet links with TorrentFast" (per-user registration, no admin rights needed).
- Single instance: opening a magnet while the app is running adds it to the open window.
- Settings: language (Spanish/English), download folder picker, phone access toggle.
- Per-torrent "open folder" and global pause/resume all.
- File properties (author, version) on the `.exe`.
- English README with Spanish translation (`README.es.md`).

### Changed
- App state (queue, resume data, settings) now lives in `%APPDATA%\TorrentFast` instead of the download folder.
- The web API listens only on `127.0.0.1` unless phone access is enabled.
- CI now launches the real window on Windows and tests magnet hand-off before publishing.

## [1.0.0] - 2026-11-07
### Added
- libtorrent 2.x engine tuned for speed (up to 2,000 connections, DHT, LSD, UPnP/NAT-PMP, extra trackers, encryption).
- Color-coded web interface with filters, focus mode and phone access.
- Magnets and `.torrent` files, sequential download, pause/resume and resume after restart.
- Command-line version (`TorrentFast-CLI.exe`).
- Automatic Windows `.exe` builds with GitHub Actions.

[1.3.0]: https://github.com/adrngza83/torrentfast/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/adrngza83/torrentfast/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/adrngza83/torrentfast/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/adrngza83/torrentfast/releases/tag/v1.0.0
