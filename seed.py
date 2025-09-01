import os, sqlite3, pathlib

db_path = os.environ.get("DATABASE_PATH", "banos.db")
schema_path = os.environ.get("SCHEMA_PATH", "schema.sql")

banos = [
  ("B-A1-H1","Baño Hombres Ala 1 - Piso 1","Ala 1","1","Hombres",1),
  ("B-A1-M1","Baño Mujeres Ala 1 - Piso 1","Ala 1","1","Mujeres",1),
  ("B-A2-H2","Baño Hombres Ala 2 - Piso 2","Ala 2","2","Hombres",1),
]

con = sqlite3.connect(db_path); cur = con.cursor()
cur.executescript(pathlib.Path(schema_path).read_text(encoding="utf-8"))

# UPSERT simple
for row in banos:
    cur.execute(
        "INSERT INTO banos(id,nombre,zona,piso,sexo,activo) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "nombre=excluded.nombre, zona=excluded.zona, piso=excluded.piso, "
        "sexo=excluded.sexo, activo=excluded.activo",
        row
    )

con.commit(); con.close()
print("OK seed →", db_path)
