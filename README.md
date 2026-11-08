# ⚡ TorrentFast

Descargador de torrents **rápido**, con interfaz web de colores que también funciona desde el celular.
Creado por **Adrián Garza Garza** ([@adrngza83](https://github.com/adrngza83)).

## Descargar

👉 Ve a [**Releases**](../../releases/latest), baja **`TorrentFast.exe`** y dale doble clic. No necesitas instalar nada.
Se abre solo en tu navegador en `http://localhost:8800`.

> La primera vez, Windows puede mostrar "Windows protegió tu PC" porque el .exe no está firmado: da clic en *Más información → Ejecutar de todas formas*. También acepta el aviso del firewall para que lleguen más peers.

## Qué tiene

- 🎨 **Colores por estado**: 🔵 descargando · 🟡 buscando datos · 🟢 listo · ⚪ pausado · 🔴 error
- 🎯 **Modo enfoque**: oculta lo que ya terminó
- 📱 **Desde el celular**: entra a `http://IP-de-tu-PC:8800` estando en la misma WiFi
- 🧲 Enlaces magnet y archivos `.torrent` (puedes subir varios)
- ▤ **Descarga secuencial** para ver un video mientras se descarga
- ⏯ Pausar y reanudar; si cierras el programa, sigue donde se quedó

## Por qué es rápido

Usa [libtorrent](https://libtorrent.org) (el motor de qBittorrent y Deluge) con ajustes agresivos:
- Hasta 2000 conexiones y 200 conexiones nuevas por segundo
- Muchas peticiones simultáneas a cada peer
- DHT, descubrimiento en red local y 10 trackers públicos extra para encontrar peers rápido
- Abre el puerto del router solo (UPnP/NAT-PMP)
- Cifrado activado para evitar que tu proveedor de internet frene las descargas

**Tip:** abre el puerto **6881 (TCP y UDP)** en tu router si UPnP no funciona; es lo que más sube la velocidad.

## Versión de terminal

```
TorrentFast-CLI.exe "magnet:?xt=urn:btih:..."
TorrentFast-CLI.exe archivo.torrent -o D:\Descargas --seq
TorrentFast-CLI.exe lista.txt --seed 1.5 --max-down 5000
```

## Desde el código

```
pip install -r requirements.txt
python torrentfast_web.py        # interfaz web
python torrentfast.py MAGNET     # terminal
```

Cada cambio en `main` compila el `.exe` en Windows con GitHub Actions y publica una versión nueva.

## Uso responsable

Úsalo para contenido que tengas derecho a descargar: distribuciones de Linux, contenido libre o con licencia abierta, y tus propios archivos.

## Licencia

MIT © 2026 Adrián Garza Garza
