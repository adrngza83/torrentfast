@echo off
title TorrentFast
cd /d "%~dp0"
where python >nul 2>&1 || (echo No encontre Python. Instalalo desde https://www.python.org/downloads/ marcando "Add to PATH". & pause & exit /b)
python -c "import libtorrent" >nul 2>&1 || (echo Instalando libtorrent la primera vez... & python -m pip install --upgrade libtorrent)
netsh advfirewall firewall show rule name="TorrentFast P2P" >nul 2>&1 || (
  echo Pidiendo permiso para abrir el puerto 6881 en el firewall...
  powershell -Command "Start-Process cmd -Verb RunAs -ArgumentList '/c netsh advfirewall firewall add rule name=\"TorrentFast P2P\" dir=in action=allow protocol=TCP localport=6881 & netsh advfirewall firewall add rule name=\"TorrentFast P2P UDP\" dir=in action=allow protocol=UDP localport=6881'"
)
python torrentfast_web.py %*
pause
