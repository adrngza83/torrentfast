# Cómo contribuir

¡Gracias por tu interés! 

1. Haz un fork y crea una rama: `git checkout -b mejora/lo-que-sea`
2. Instala dependencias: `pip install -r requirements.txt`
3. Prueba tu cambio: `python torrentfast_web.py` y abre `http://localhost:8800`
4. Abre un Pull Request explicando qué cambia y por qué. GitHub Actions compila y prueba el `.exe` automáticamente.

**Estilo:** Python 3.12, PEP 8, textos de la interfaz en español.
**Colores de estado** (no cambiar su significado): azul = descargando, amarillo = buscando, verde = listo, gris = pausado, rojo = error.
