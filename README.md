# Sistema de Reportes de Baños (QR)

MVP con **QR por baño** + **formulario PWA** + **reportes** (Chart.js).
- Sin severidad.
- Filtros por fecha, zona y baño en el dashboard.

## Inicio rápido
```bash
pip install -r requirements.txt
python seed.py
python app.py  # http://localhost:8000
# Form QR:   http://localhost:8000/qr?r=B-A1-H1
# Reportes:  http://localhost:8000/reportes
```

## Generar QR
```bash
set QR_BASE_URL=http://localhost:8000/qr  # PS: $env:QR_BASE_URL="..."
python make_qr.py
```

## Producción
```bash
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:application
```
