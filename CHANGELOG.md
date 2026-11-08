# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/).

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

[1.1.0]: https://github.com/adrngza83/torrentfast/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/adrngza83/torrentfast/releases/tag/v1.0.0
