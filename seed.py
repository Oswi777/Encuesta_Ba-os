import os
import sqlite3
import pathlib

# Lee ruta de BD desde env (coincide con Render: /data/banos.db)
db_path = os.getenv("DATABASE_PATH", "banos.db")
schema_path = "schema.sql"

# Asegura carpeta contenedora (por si es /data/...)
pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

banos = [
    ("RH-PB-H", "Baños RH – Planta Baja Hombres", "RH", "PB", "Hombres", 1),
    ("RH-PB-M", "Baños RH – Planta Baja Mujeres", "RH", "PB", "Mujeres", 1),
    ("RH-PA-H", "Baños RH – Planta Alta Hombres", "RH", "PA", "Hombres", 1),
    ("RH-PA-M", "Baños RH – Planta Alta Mujeres", "RH", "PA", "Mujeres", 1),

    # Planta 1
    ("P1-ADM-H", "Baños Planta 1 – Administrativos Hombres", "Planta 1", "1", "Hombres", 1),
    ("P1-ADM-M", "Baños Planta 1 – Administrativos Mujeres", "Planta 1", "1", "Mujeres", 1),
    ("P1-PROD-H", "Baños Planta 1 – Producción Hombres", "Planta 1", "1", "Hombres", 1),
    ("P1-PROD-M", "Baños Planta 1 – Producción Mujeres", "Planta 1", "1", "Mujeres", 1),

    # Planta 2
    ("P2-H", "Baños Planta 2 Hombres", "Planta 2", "2", "Hombres", 1),
    ("P2-M", "Baños Planta 2 Mujeres", "Planta 2", "2", "Mujeres", 1),

    # Planta 3
    ("P3-H", "Baños Planta 3 Hombres", "Planta 3", "3", "Hombres", 1),
    ("P3-M", "Baños Planta 3 Mujeres", "Planta 3", "3", "Mujeres", 1),
]

con = sqlite3.connect(db_path); cur = con.cursor()
cur.executescript(pathlib.Path(schema_path).read_text(encoding="utf-8"))
cur.executemany(
    "INSERT OR REPLACE INTO banos(id,nombre,zona,piso,sexo,activo) VALUES(?,?,?,?,?,?)",
    banos
)
con.commit(); con.close()
print("OK seed →", db_path)
