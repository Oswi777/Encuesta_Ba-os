from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import os, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from models import SessionLocal, init_db, Bano, Reporte
from sqlalchemy import select, func, desc

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # 3 MB
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    DEFAULT_TZ = os.getenv("DEFAULT_TZ", "America/Mexico_City")
    def get_tz_from_request():
        tz_str = (request.args.get("tz") or DEFAULT_TZ).strip()
        try:
            return ZoneInfo(tz_str)
        except Exception:
            return ZoneInfo(DEFAULT_TZ)

    # Crea tablas si no existen (dev/test). En prod usarás siempre Postgres ya listo.
    try:
        init_db()
    except Exception as e:
        app.logger.warning(f"DB init warning: {e}")

    @app.route("/")
    def index():
        return redirect(url_for("reportes_page"))

    # ---------- QR FORM ----------
    @app.route("/qr", methods=["GET"])
    def qr_form():
        id_bano = (request.args.get("r") or "").strip()
        db = SessionLocal()
        try:
            b = db.get(Bano, id_bano)
            if not b or not b.activo:
                return render_template("not_found.html"), 404
            return render_template("qr_form.html", bano={"id": b.id, "nombre": b.nombre, "zona": b.zona, "piso": b.piso, "sexo": b.sexo})
        finally:
            db.close()

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
            allowed = {"png", "jpg", "jpeg", "webp"}
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            if ext not in allowed:
                return jsonify({"ok": False, "error": "Extensión no permitida"}), 400
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S_")
            fname = ts + secure_filename(f.filename)
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            f.save(fpath)
            foto_url = f"/uploads/{fname}"

        db = SessionLocal()
        try:
            b = db.get(Bano, id_bano)
            if not b or not b.activo:
                return jsonify({"ok": False, "error": "Baño inválido"}), 400

            r = Reporte(
                id_bano=id_bano, categoria=categoria, comentario=comentario,
                foto_url=foto_url, creado_por_ip=request.remote_addr, origen="qr"
            )
            db.add(r); db.commit()
            return jsonify({"ok": True, "reporte_id": r.id})
        finally:
            db.close()

    @app.route("/uploads/<path:fname>")
    def uploads(fname):
        return send_from_directory(app.config["UPLOAD_FOLDER"], fname)

    # ---------- API: catálogo de baños ----------
    @app.route("/api/banos")
    def api_banos():
        db = SessionLocal()
        try:
            stmt = select(Bano).where(Bano.activo == True).order_by(Bano.zona, Bano.piso, Bano.nombre)
            rows = db.execute(stmt).scalars().all()
            return jsonify([{
                "id": x.id, "nombre": x.nombre, "zona": x.zona, "piso": x.piso, "sexo": x.sexo, "activo": x.activo
            } for x in rows])
        finally:
            db.close()

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

        db = SessionLocal()
        try:
            q = db.query(Reporte, Bano).join(Bano, Bano.id == Reporte.id_bano)
            if desde: q = q.filter(func.date(Reporte.creado_en) >= desde)
            if hasta: q = q.filter(func.date(Reporte.creado_en) <= hasta)
            if zona:  q = q.filter(Bano.zona == zona)
            if id_b:  q = q.filter(Reporte.id_bano == id_b)
            if search:
                like = f"%{search}%"
                q = q.filter(
                    (Reporte.categoria.ilike(like)) | (Reporte.comentario.ilike(like)) |
                    (Bano.nombre.ilike(like)) | (Bano.id.ilike(like)) |
                    (Bano.zona.ilike(like)) | (Bano.piso.ilike(like))
                )

            total = q.count()
            pages = max(1, (total + per_page - 1) // per_page)

            items = []
            for rep, b in q.order_by(desc(Reporte.creado_en)).limit(per_page).offset(offset).all():
                try:
                    creado_local = rep.creado_en.astimezone(tzinfo).isoformat()
                except Exception:
                    creado_local = rep.creado_en.isoformat() if rep.creado_en else None
                items.append({
                    "id": rep.id,
                    "creado_en": rep.creado_en.isoformat() if rep.creado_en else None,
                    "creado_local": creado_local,
                    "categoria": rep.categoria,
                    "comentario": rep.comentario,
                    "foto_url": rep.foto_url,
                    "id_bano": b.id,
                    "nombre_bano": b.nombre,
                    "zona": b.zona,
                    "piso": b.piso,
                    "sexo": b.sexo
                })

            return jsonify({"page": page, "per_page": per_page, "total": total, "pages": pages, "items": items})
        finally:
            db.close()

    # ---------- API: KPIs ----------
    @app.route("/api/kpis")
    def kpis():
        desde = request.args.get("desde")
        hasta = request.args.get("hasta")
        zona  = request.args.get("zona")
        id_b  = request.args.get("id_bano")
        tzinfo = get_tz_from_request()

        db = SessionLocal()
        try:
            q = db.query(Reporte.categoria, Reporte.creado_en, Reporte.id_bano, Bano.zona).join(Bano, Bano.id == Reporte.id_bano)
            if desde: q = q.filter(func.date(Reporte.creado_en) >= desde)
            if hasta: q = q.filter(func.date(Reporte.creado_en) <= hasta)
            if zona:  q = q.filter(Bano.zona == zona)
            if id_b:  q = q.filter(Reporte.id_bano == id_b)
            rows = q.all()

            total = len(rows)

            # catálogo de baños activos
            cat_banos = {b.id: {"id": b.id, "nombre": b.nombre, "zona": b.zona, "piso": b.piso}
                         for b in db.query(Bano).filter(Bano.activo == True).all()}

            por_categoria, por_bano, por_dia, por_zona = {}, {}, {}, {}
            for categoria, creado_en, id_bano, z in rows:
                por_categoria[categoria] = por_categoria.get(categoria, 0) + 1
                por_bano[id_bano] = por_bano.get(id_bano, 0) + 1
                por_zona[z] = por_zona.get(z, 0) + 1
                try:
                    dloc = creado_en.astimezone(tzinfo).date().isoformat()
                except Exception:
                    dloc = creado_en.date().isoformat()
                por_dia[dloc] = por_dia.get(dloc, 0) + 1

            top_banos = sorted(
                [{"id_bano": k, "nombre": cat_banos.get(k, {}).get("nombre", k), "total": v}
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
                "banos_catalogo": cat_banos
            })
        finally:
            db.close()

    # --- Encuesta/kiosco sin QR ---
    @app.route("/encuesta")
    def encuesta_page():
        return render_template("encuesta.html")

    # ---------- Reportes (HTML estático) ----------
    @app.route("/reportes")
    def reportes_page():
        return app.send_static_file("reportes/reportes.html")

    @app.route("/api/health")
    def health():
        try:
            db = SessionLocal()
            db.execute(select(func.now()))
            db.close()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "err": str(e)}, 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
