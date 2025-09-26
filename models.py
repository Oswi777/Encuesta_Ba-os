"""
Modelos y acceso a datos para el Sistema de Reportes de Baños.

- Soporta PostgreSQL (Render) y SQLite (local).
- Normaliza 'postgres://' a 'postgresql+psycopg2://'.
- Expone helpers para uso sencillo desde los endpoints Flask.

Uso típico en app.py:

    from models import (
        SessionLocal, init_db, Bano, Reporte,
        get_banos, create_reporte, list_reportes, fetch_rows_for_kpis
    )

    # Crear tablas al arrancar si no existen
    init_db()

    # Dentro de una vista:
    with SessionLocal() as s:
        banos = get_banos(s)  # lista de dicts

"""

from __future__ import annotations
import os
import math
import datetime
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import (
    create_engine, String, Integer, Boolean, DateTime, Text, ForeignKey,
    func, select, Index
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import (
    declarative_base, relationship, Mapped, mapped_column, sessionmaker, Session
)

# ============== Normalización de URL de BD ===================

def normalize_database_url(raw: Optional[str]) -> str:
    """
    Render/Heroku entregan 'postgres://...' y SQLAlchemy requiere
    'postgresql+psycopg2://...'. También soporta sqlite por defecto.
    """
    if not raw or not raw.strip():
        return "sqlite:///banos.db"

    url = raw.strip()
    # Heroku/Render style
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    # Si es 'postgresql://' sin driver, añade psycopg2
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))
# Permite override local para desarrollo
DATABASE_URL = normalize_database_url(os.getenv("DB_URL", DATABASE_URL))

# Engine y Session configurados para ambos motores
engine_kwargs: Dict[str, Any] = dict(pool_pre_ping=True, future=True)

# SQLite necesita connect_args especiales
if DATABASE_URL.startswith("sqlite:"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)

Base = declarative_base()

# =================== Modelos ================================

class Bano(Base):
    __tablename__ = "banos"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # ej: "B-A1-H1"
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    zona: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    piso: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sexo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    reportes: Mapped[List["Reporte"]] = relationship("Reporte", back_populates="bano", cascade="all,delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "zona": self.zona,
            "piso": self.piso,
            "sexo": self.sexo,
            "activo": bool(self.activo),
        }


class Reporte(Base):
    __tablename__ = "reportes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_bano: Mapped[str] = mapped_column(String, ForeignKey("banos.id", ondelete="CASCADE"), nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    comentario: Mapped[Optional[str]] = mapped_column(Text)
    foto_url: Mapped[Optional[str]] = mapped_column(String)
    origen: Mapped[str] = mapped_column(String, default="qr", server_default="qr")
    # Importante: usa timezone-aware en Postgres; en SQLite se guarda naive
    creado_en: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    creado_por_ip: Mapped[Optional[str]] = mapped_column(String)
    # La columna 'estado' existe en el schema, pero no la usamos para KPIs
    estado: Mapped[Optional[str]] = mapped_column(String, default="abierto", server_default="abierto")

    bano: Mapped[Bano] = relationship("Bano", back_populates="reportes")

    def to_dict_joined(self) -> Dict[str, Any]:
        """Devuelve un dict con columnas del reporte y del baño (si está cargado)."""
        d = {
            "id": self.id,
            "id_bano": self.id_bano,
            "categoria": self.categoria,
            "comentario": self.comentario,
            "foto_url": self.foto_url,
            "origen": self.origen,
            "creado_en": self.creado_en.isoformat() if isinstance(self.creado_en, datetime.datetime) else self.creado_en,
            "creado_por_ip": self.creado_por_ip,
            "estado": self.estado,
        }
        if self.bano is not None:
            d.update({
                "nombre_bano": self.bano.nombre,
                "zona": self.bano.zona,
                "piso": self.bano.piso,
                "sexo": self.bano.sexo,
            })
        return d


# Índices adicionales (equivalentes a schema.sql)
Index("idx_reportes_bano_fecha", Reporte.id_bano, Reporte.creado_en.desc())
Index("idx_reportes_categoria", Reporte.categoria)
Index("idx_reportes_estado", Reporte.estado)

# =================== Utilidades =============================

def init_db() -> None:
    """Crea tablas si no existen (útil para el primer deploy en Render)."""
    Base.metadata.create_all(bind=engine)


# =================== Helpers de consulta ====================

def get_banos(s: Session, solo_activos: bool = True) -> List[Dict[str, Any]]:
    q = select(Bano)
    if solo_activos:
        q = q.where(Bano.activo.is_(True))
    # Orden sugerido: zona, piso, nombre
    q = q.order_by(Bano.zona.nulls_last(), Bano.piso.nulls_last(), Bano.nombre)
    return [b.to_dict() for b in s.scalars(q).all()]


def create_reporte(
    s: Session,
    *,
    id_bano: str,
    categoria: str,
    comentario: Optional[str] = None,
    foto_url: Optional[str] = None,
    origen: str = "qr",
    creado_por_ip: Optional[str] = None,
) -> int:
    # Validación básica de baño activo
    b = s.get(Bano, id_bano)
    if not b or not b.activo:
        raise ValueError("Baño inválido o inactivo")

    rep = Reporte(
        id_bano=id_bano,
        categoria=categoria,
        comentario=comentario,
        foto_url=foto_url,
        origen=origen,
        creado_por_ip=creado_por_ip,
    )
    s.add(rep)
    s.commit()
    s.refresh(rep)
    return rep.id


def list_reportes(
    s: Session,
    *,
    desde: Optional[str] = None,   # 'YYYY-MM-DD'
    hasta: Optional[str] = None,   # 'YYYY-MM-DD'
    zona: Optional[str] = None,
    id_bano: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
) -> Dict[str, Any]:
    """
    Devuelve un dict con paginación: {page, per_page, total, pages, items}
    items incluye datos del baño (join).
    """
    # Base
    q = select(Reporte).join(Bano).where(Bano.id == Reporte.id_bano)
    # Filtros
    if desde:
        # cast a date usando la parte de fecha del timestamp
        q = q.where(func.date(Reporte.creado_en) >= desde)
    if hasta:
        q = q.where(func.date(Reporte.creado_en) <= hasta)
    if zona:
        q = q.where(Bano.zona == zona)
    if id_bano:
        q = q.where(Reporte.id_bano == id_bano)
    if search:
        like = f"%{search}%"
        q = q.where(
            (Reporte.categoria.ilike(like)) |
            (Reporte.comentario.ilike(like)) |
            (Bano.nombre.ilike(like)) |
            (Bano.id.ilike(like)) |
            (Bano.zona.ilike(like)) |
            (Bano.piso.ilike(like))
        )

    # Total
    total = s.scalar(select(func.count()).select_from(q.subquery()))
    pages = max(1, math.ceil(total / per_page)) if total else 1
    page = max(1, min(page, pages))
    offset = (page - 1) * per_page

    # Página de resultados (más recientes primero)
    q_page = (
        q.order_by(Reporte.creado_en.desc())
         .offset(offset)
         .limit(per_page)
    )
    rows = s.scalars(q_page).all()
    # Asegura que relationship bano esté cargado para to_dict_joined
    # (la join ya lo hace, pero por si acaso)
    items = [r.to_dict_joined() for r in rows]

    return {
        "page": page,
        "per_page": per_page,
        "total": int(total or 0),
        "pages": pages,
        "items": items,
    }


def fetch_rows_for_kpis(
    s: Session,
    *,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    zona: Optional[str] = None,
    id_bano: Optional[str] = None,
) -> List[Tuple[str, datetime.datetime, str, Optional[str]]]:
    """
    Devuelve filas simples para armar KPIs en Python (como ya lo haces en app.py):
    [(categoria, creado_en, id_bano, zona)]
    Así mantienes la lógica de agrupar por día local en el backend con tz.
    """
    q = select(
        Reporte.categoria,
        Reporte.creado_en,
        Reporte.id_bano,
        Bano.zona,
    ).join(Bano)

    if desde:
        q = q.where(func.date(Reporte.creado_en) >= desde)
    if hasta:
        q = q.where(func.date(Reporte.creado_en) <= hasta)
    if zona:
        q = q.where(Bano.zona == zona)
    if id_bano:
        q = q.where(Reporte.id_bano == id_bano)

    q = q.order_by(Reporte.creado_en.desc())

    return [(c, ce, ib, z) for c, ce, ib, z in s.execute(q).all()]
