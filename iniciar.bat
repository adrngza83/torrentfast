@echo off
rem Run TorrentFast from source (for developers). Regular users: download TorrentFast.exe from Releases.
cd /d "%~dp0"
python -c "import libtorrent, webview" >nul 2>&1 || python -m pip install -r requirements.txt
start "" pythonw torrentfast_app.py %*
