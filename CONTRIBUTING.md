# Contributing

Thanks for your interest in TorrentFast!

1. Fork the repo and create a branch: `git checkout -b feature/my-change`
2. Install dependencies: `pip install -r requirements.txt`
3. Run it: `python torrentfast_app.py` (desktop) or `python torrentfast_web.py` (browser)
4. Quick check: `python torrentfast_app.py --selftest` must print `SELFTEST OK`
5. Open a pull request explaining what changed and why. GitHub Actions builds the `.exe` and launches it on Windows.

**Style:** Python 3.12, PEP 8. Every user-facing string goes in both languages in `ui/index.html` (`I18N.es` and `I18N.en`).

**Status colors** (keep their meaning consistent): blue = downloading, yellow = fetching metadata, green = completed, gray = paused, red = error.
