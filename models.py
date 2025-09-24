# models.py
import os
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func, Index, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# En contenedor/producción define DATABASE_URL=postgresql+psycopg2://...
# En local (sin enviarla) cae a SQLite (útil para pruebas)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///banos.db")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

class Bano(Base):
    __tablename__ = "banos"
    id = Column(String(32), primary_key=True)   # ej: "B-A1-H1"
    nombre = Column(Text, nullable=False)
    zona = Column(String(64))
    piso = Column(String(16))
    sexo = Column(String(16))
    activo = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_banos_zona", "zona"),
    )

class Reporte(Base):
    __tablename__ = "reportes"
    id = Column(Integer, primary_key=True)
    id_bano = Column(String(32), ForeignKey("banos.id", ondelete="RESTRICT"), nullable=False)
    categoria = Column(String(64), nullable=False)
    comentario = Column(Text)
    foto_url = Column(Text)
    origen = Column(String(16), default="qr")
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # TIMESTAMPTZ en PG
    creado_por_ip = Column(String(64))
    estado = Column(String(16), default="abierto")

    bano = relationship("Bano")

    __table_args__ = (
        Index("idx_reportes_bano_fecha", "id_bano", "creado_en"),
        Index("idx_reportes_categoria", "categoria"),
        Index("idx_reportes_estado", "estado"),
    )

def init_db():
    Base.metadata.create_all(engine)
