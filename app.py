from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import os, sqlite3, datetime
from pathlib import Path
from zoneinfo import ZoneInfo  # Python 3.9+

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["DATABASE_PATH"] = os.getenv("DATABASE_PATH", "banos.db")
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    def db():
        conn = sqlite3.connect(app.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        return conn

    # ---- Helpers de fecha/Zona Horaria ----
    DEFAULT_TZ = "America/Monterrey"

    def get_tz_from_request():
        tz_str = (request.args.get("tz") or DEFAULT_TZ).strip()
        try:
            return ZoneInfo(tz_str)
        except Exception:
            return ZoneInfo(DEFAULT_TZ)

    def parse_sqlite_ts_utc(ts: str) -> datetime.datetime:
        """
        Acepta 'YYYY-MM-DD HH:MM:SS' o 'YYYY-MM-DD HH:MM:SS.%f' en UTC (SQLite CURRENT_TIMESTAMP).
        Devuelve datetime con tzinfo=UTC.
        """
        ts = ts.strip()
        try:
            dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=datetime.timezone.utc)

    @app.route("/")
    def index():
        return redirect(url_for("reportes_page"))

    # ---------- QR FORM ----------
    @app.route("/qr", methods=["GET"])
    def qr_form():
        id_bano = (request.args.get("r") or "").strip()
        con = db(); cur = con.cursor()
        cur.execute("SELECT * FROM banos WHERE id=? AND activo=1", (id_bano,))
        bano = cur.fetchone()
        if not bano:
            return render_template("not_found.html"), 404
        return render_template("qr_form.html", bano=bano)

    # ---------- API: crear reporte ----------
    @app.route("/api/reportes", methods=["POST"])
    def crear_reporte():
        data = request.form
        id_bano = (data.get("id_bano") or "").strip()
        categoria = (data.get("categoria") or "").strip()
        comentario = (data.get("comentario") or "").strip()

        if not id_bano or not categoria:
            return jsonify({"ok": False, "error": "Faltan campos"}), 400

        # foto opcional
        foto_url = None
        if "foto" in request.files and request.files["foto"].filename:
            f = request.files["foto"]
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S_")
            fname = ts + secure_filename(f.filename)
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            f.save(fpath)
            foto_url = f"/uploads/{fname}"

        con = db(); cur = con.cursor()
        # validar baño
        cur.execute("SELECT 1 FROM banos WHERE id=? AND activo=1", (id_bano,))
        if not cur.fetchone():
            return jsonify({"ok": False, "error": "Baño inválido"}), 400

        cur.execute(
            """INSERT INTO reportes(id_bano, categoria, comentario, foto_url, creado_por_ip)
               VALUES(?,?,?,?,?)""",
            (id_bano, categoria, comentario, foto_url, request.remote_addr)
        )
        con.commit()
        rep_id = cur.lastrowid
        return jsonify({"ok": True, "reporte_id": rep_id})

    @app.route("/uploads/<path:fname>")
    def uploads(fname):
        return send_from_directory(app.config["UPLOAD_FOLDER"], fname)

    # ---------- API: catálogo de baños ----------
    @app.route("/api/banos")
    def api_banos():
        con = db(); cur = con.cursor()
        cur.execute("SELECT * FROM banos WHERE activo=1 ORDER BY zona, piso, nombre")
        return jsonify([dict(x) for x in cur.fetchall()])

    # ---------- API: lista paginada de reportes ----------
    @app.route("/api/reportes_list")
    def reportes_list():
        desde = request.args.get("desde")
        hasta = request.args.get("hasta")
        zona  = request.args.get("zona")
        id_b  = request.args.get("id_bano")
        search = (request.args.get("q") or "").strip()

        tzinfo = get_tz_from_request()

        page = int(request.args.get("page", 1))
        per_page = max(5, min(50, int(request.args.get("per_page", 10))))
        offset = (page - 1) * per_page

        con = db(); cur = con.cursor()
        base = " FROM reportes r JOIN banos b ON b.id = r.id_bano WHERE 1=1 "
        wh, params = "", []
        if desde:
            wh += " AND date(r.creado_en) >= date(?)"; params.append(desde)
        if hasta:
            wh += " AND date(r.creado_en) <= date(?)"; params.append(hasta)
        if zona:
            wh += " AND b.zona = ?"; params.append(zona)
        if id_b:
            wh += " AND r.id_bano = ?"; params.append(id_b)
        if search:
            like = f"%{search}%"
            wh += (" AND (r.categoria LIKE ? OR r.comentario LIKE ? OR "
                   "b.nombre LIKE ? OR b.id LIKE ? OR b.zona LIKE ? OR b.piso LIKE ?)")
            params += [like, like, like, like, like, like]

        # total
        cur.execute("SELECT COUNT(*) " + base + wh, params)
        total = cur.fetchone()[0]
        pages = max(1, (total + per_page - 1) // per_page)

        # datos (más recientes primero)
        cur.execute(
            "SELECT r.id, r.creado_en, r.categoria, r.comentario, r.foto_url, "
            "b.id AS id_bano, b.nombre AS nombre_bano, b.zona, b.piso, b.sexo "
            + base + wh + " ORDER BY r.creado_en DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        )

        items = []
        for row in cur.fetchall():
            it = dict(row)
            try:
                dt_utc = parse_sqlite_ts_utc(it["creado_en"])
                it["creado_local"] = dt_utc.astimezone(tzinfo).isoformat()
            except Exception:
                it["creado_local"] = it["creado_en"]  # fallback si viniera en otro formato
            items.append(it)

        return jsonify({
            "page": page, "per_page": per_page, "total": total, "pages": pages,
            "items": items
        })

    # ---------- API: KPIs con filtros (fechas por DÍA LOCAL) ----------
    @app.route("/api/kpis")
    def kpis():
        desde = request.args.get("desde")
        hasta = request.args.get("hasta")
        zona  = request.args.get("zona")
        id_b  = request.args.get("id_bano")
        tzinfo = get_tz_from_request()

        con = db(); cur = con.cursor()
        q = ("SELECT r.categoria, r.creado_en, r.id_bano, b.zona "
             "FROM reportes r JOIN banos b ON b.id = r.id_bano WHERE 1=1")
        params = []
        if desde:
            q += " AND date(r.creado_en) >= date(?)"; params.append(desde)
        if hasta:
            q += " AND date(r.creado_en) <= date(?)"; params.append(hasta)
        if zona:
            q += " AND b.zona = ?"; params.append(zona)
        if id_b:
            q += " AND r.id_bano = ?"; params.append(id_b)

        cur.execute(q, params)
        rows = cur.fetchall()

        total = len(rows)

        cur.execute("SELECT id, nombre, zona, piso FROM banos WHERE activo=1")
        banos_map = {r["id"]: dict(r) for r in cur.fetchall()}

        por_categoria, por_bano, por_dia, por_zona = {}, {}, {}, {}
        for r in rows:
            por_categoria[r["categoria"]] = por_categoria.get(r["categoria"], 0) + 1
            por_bano[r["id_bano"]] = por_bano.get(r["id_bano"], 0) + 1
            por_zona[r["zona"]] = por_zona.get(r["zona"], 0) + 1

            # agrupa por DÍA LOCAL (robusto a microsegundos)
            try:
                dt_utc = parse_sqlite_ts_utc(r["creado_en"])
                dloc = dt_utc.astimezone(tzinfo).date().isoformat()
            except Exception:
                dloc = r["creado_en"].split(" ")[0]
            por_dia[dloc] = por_dia.get(dloc, 0) + 1

        top_banos = sorted(
            [{"id_bano": k, "nombre": banos_map.get(k, {}).get("nombre", k), "total": v}
             for k, v in por_bano.items()],
            key=lambda x: x["total"], reverse=True
        )[:10]

        return jsonify({
            "total_reportes": total,
            "por_categoria": por_categoria,
            "por_bano": por_bano,
            "por_dia": por_dia,
            "por_zona": por_zona,
            "top_banos": top_banos,
            "banos_catalogo": banos_map
        })

    # --- Encuesta/kiosco sin QR ---
    @app.route("/encuesta")
    def encuesta_page():
        # Página para iPad: el usuario elige el baño y luego reporta
        return render_template("encuesta.html")

    # ---------- Reportes (sirve el HTML estático) ----------
    @app.route("/reportes")
    def reportes_page():
        return app.send_static_file("reportes/reportes.html")

    @app.route("/api/health")
    def health():
        try:
            con = db(); con.execute("SELECT 1"); con.close()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "err": str(e)}, 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
