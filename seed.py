# seed.py
from models import init_db, SessionLocal, Bano

BANOS = [
  Bano(id="B-A1-H1", nombre="Baño Hombres Ala 1 - Piso 1", zona="Ala 1", piso="1", sexo="Hombres", activo=True),
  Bano(id="B-A1-M1", nombre="Baño Mujeres Ala 1 - Piso 1", zona="Ala 1", piso="1", sexo="Mujeres", activo=True),
  Bano(id="B-A2-H2", nombre="Baño Hombres Ala 2 - Piso 2", zona="Ala 2", piso="2", sexo="Hombres", activo=True),
]

def main():
    init_db()
    db = SessionLocal()
    try:
        for b in BANOS:
            cur = db.get(Bano, b.id)
            if cur:
                cur.nombre, cur.zona, cur.piso, cur.sexo, cur.activo = b.nombre, b.zona, b.piso, b.sexo, b.activo
            else:
                db.add(b)
        db.commit()
        print("OK seed")
    finally:
        db.close()

if __name__ == "__main__":
    main()
