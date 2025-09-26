import os
import sqlite3
import pathlib

# Lee ruta de BD desde env (coincide con Render: /data/banos.db)
db_path = os.getenv("DATABASE_PATH", "banos.db")
schema_path = "schema.sql"

# Asegura carpeta contenedora (por si es /data/...)
pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

banos = [
  ("B-A1-H1","Baño Hombres Ala 1 - Piso 1","Ala 1","1","Hombres",1),
  ("B-A1-M1","Baño Mujeres Ala 1 - Piso 1","Ala 1","1","Mujeres",1),
  ("B-A2-H2","Baño Hombres Ala 2 - Piso 2","Ala 2","2","Hombres",1),
]

con = sqlite3.connect(db_path); cur = con.cursor()
cur.executescript(pathlib.Path(schema_path).read_text(encoding="utf-8"))
cur.executemany(
    "INSERT OR REPLACE INTO banos(id,nombre,zona,piso,sexo,activo) VALUES(?,?,?,?,?,?)",
    banos
)
con.commit(); con.close()
print("OK seed →", db_path)
