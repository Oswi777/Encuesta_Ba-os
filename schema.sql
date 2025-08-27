PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS banos (
  id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  zona TEXT,
  piso TEXT,
  sexo TEXT,
  activo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reportes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_bano TEXT NOT NULL,
  categoria TEXT NOT NULL,
  comentario TEXT,
  foto_url TEXT,
  origen TEXT DEFAULT 'qr',
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
  creado_por_ip TEXT,
  estado TEXT DEFAULT 'abierto',
  FOREIGN KEY (id_bano) REFERENCES banos(id)
);

CREATE INDEX IF NOT EXISTS idx_reportes_bano_fecha ON reportes(id_bano, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_reportes_categoria ON reportes(categoria);
CREATE INDEX IF NOT EXISTS idx_reportes_estado ON reportes(estado);
