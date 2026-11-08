<p align="center"><img src="assets/icon.png" width="96" alt="Ícono de TorrentFast"></p>

<h1 align="center">TorrentFast</h1>

<p align="center">
Descargador de torrents rápido, con apariencia de app nativa de Windows.<br>
Creado por <b>Adrián Garza Garza</b> (<a href="https://github.com/adrngza83">@adrngza83</a>)
</p>

<p align="center"><a href="README.md">English</a> · <b>Español</b></p>

---

## Descargar

1. Entra a [**Releases**](https://github.com/adrngza83/torrentfast/releases/latest) y baja **`TorrentFast.exe`**.
2. Dale doble clic. No hay que instalar nada.

> **La primera vez:** Windows puede decir *"Windows protegió tu PC"* porque la app todavía no está firmada. Da clic en **Más información → Ejecutar de todas formas**. Cuando el firewall pregunte, permite **redes privadas** para que te lleguen más peers.

## Qué tiene

- 🪟 **Se ve como app de Windows 11**: ventana propia, tema claro/oscuro según tu Windows, íconos Fluent
- 🎨 **Colores por estado**: 🔵 descargando · 🟡 buscando datos · 🟢 completado · ⚪ pausado · 🔴 error
- 🎯 **Modo enfoque**: oculta lo terminado y lo pausado
- 📋 **Pega un magnet con Ctrl+V** en cualquier parte de la ventana, o **arrastra archivos `.torrent`**
- 🧲 **Abrir magnets con TorrentFast**: un clic en Configuración y cada magnet que abras en tu navegador llega directo a la app
- ▶️ **Descarga secuencial** para ver un video mientras baja
- ⏯ Pausar/reanudar todo; si cierras la app, sigue donde se quedó
- 📱 **Desde el celular** (opcional): contrólala desde cualquier dispositivo en tu WiFi
- 🌐 Español e inglés, automático según el idioma de tu sistema

## Por qué es rápido

Usa [libtorrent](https://libtorrent.org) (el motor de qBittorrent y Deluge) con ajustes agresivos: hasta 2000 conexiones, colas profundas por peer, DHT, descubrimiento local, 10 trackers públicos extra, mapeo automático de puertos (UPnP/NAT-PMP) y cifrado contra el estrangulamiento del proveedor de internet.

**Tip:** si UPnP no funciona en tu router, abre a mano el puerto **6881 (TCP y UDP)**. Es lo que más sube la velocidad.

## Versión de terminal

```
TorrentFast-CLI.exe "magnet:?xt=urn:btih:..."
TorrentFast-CLI.exe archivo.torrent -o D:\Descargas --seq
```

## Uso responsable

Úsalo para contenido que tengas derecho a descargar: distribuciones de Linux, contenido con licencia libre, obras de dominio público y tus propios archivos.

## Licencia

[MIT](LICENSE) © 2026 Adrián Garza Garza
