from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import os, datetime
from pathlib import Path
from zoneinfo import ZoneInfo  # Python 3.9+

# Importa helpers ORM (tu models.py actual ya está OK)
from models import (
    SessionLocal, init_db,
    get_banos, create_reporte, list_reportes, fetch_rows_for_kpis,
    Bano
)

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # --- Config básica ---
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # 3 MB para uploads
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # ---- Helpers de fecha / Zona Horaria ----
    DEFAULT_TZ = os.getenv("DEFAULT_TZ", "America/Monterrey")

    def get_tz_from_request():
        """
        Devuelve un tzinfo válido y robusto.
        Intenta: tz de query -> DEFAULT_TZ -> aliases MX -> UTC -> offset -6.
        """
        preferidas = [
            (request.args.get("tz") or DEFAULT_TZ).strip(),
            "America/Matamoros",
            "America/Mexico_City",
        ]
        for key in preferidas:
            try:
                return ZoneInfo(key)
            except Exception:
                continue
        try:
            return ZoneInfo("UTC")
        except Exception:
            return datetime.timezone(datetime.timedelta(hours=-6))

    # ---- Init schema + semilla (idempotente) ----
    def ensure_seed():
        """
        Crea tablas si no existen (init_db) y agrega la semilla de baños
        SOLO si la tabla 'banos' está vacía. Funciona con Postgres/SQLite.
        """
        init_db()
        seed_banos = [
            # RH
            ("RH-PB-H", "Baños RH – Planta Baja Hombres", "RH", "PB", "Hombres", True),
            ("RH-PB-M", "Baños RH – Planta Baja Mujeres", "RH", "PB", "Mujeres", True),
            ("RH-PA-H", "Baños RH – Planta Alta Hombres", "RH", "PA", "Hombres", True),
            ("RH-PA-M", "Baños RH – Planta Alta Mujeres", "RH", "PA", "Mujeres", True),
            # Planta 1
            ("P1-ADM-H",  "Baños Planta 1 – Administrativos Hombres", "Planta 1", "1", "Hombres", True),
            ("P1-ADM-M",  "Baños Planta 1 – Administrativos Mujeres", "Planta 1", "1", "Mujeres", True),
            ("P1-PROD-H", "Baños Planta 1 – Producción Hombres",     "Planta 1", "1", "Hombres", True),
            ("P1-PROD-M", "Baños Planta 1 – Producción Mujeres",     "Planta 1", "1", "Mujeres", True),
            # Planta 2
            ("P2-H", "Baños Planta 2 Hombres", "Planta 2", "2", "Hombres", True),
            ("P2-M", "Baños Planta 2 Mujeres", "Planta 2", "2", "Mujeres", True),
            # Planta 3
            ("P3-H", "Baños Planta 3 Hombres", "Planta 3", "3", "Hombres", True),
            ("P3-M", "Baños Planta 3 Mujeres", "Planta 3", "3", "Mujeres", True),
        ]
        with SessionLocal() as s:
            have_any = s.query(Bano).count() > 0
            if not have_any:
                for id_, nombre, zona, piso, sexo, activo in seed_banos:
                    s.add(Bano(id=id_, nombre=nombre, zona=zona, piso=piso, sexo=sexo, activo=bool(activo)))
                s.commit()
                print(f"[seed] Insertados {len(seed_banos)} baños.")
            else:
                print("[seed] Ya existen baños; no se inserta.")

    # Ejecuta init+seed al arrancar el proceso
    try:
        ensure_seed()
    except Exception as e:
        # No bloquea el arranque si falla la seed por permisos/conexión,
        # pero deja huella en logs para diagnosticar.
        app.logger.warning(f"Seed/init warning: {e}")

    @app.route("/")
    def index():
        return redirect(url_for("reportes_page"))

    # ---------- QR FORM ----------
    @app.route("/qr", methods=["GET"])
    def qr_form():
        id_bano = (request.args.get("r") or "").strip()
        with SessionLocal() as s:
            mapa = {b["id"]: b for b in get_banos(s, solo_activos=True)}
        bano = mapa.get(id_bano)
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
            allowed = {"png", "jpg", "jpeg", "webp"}
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            if ext not in allowed:
                return jsonify({"ok": False, "error": "Extensión no permitida"}), 400
            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S_")
            fname = ts + secure_filename(f.filename)
            fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            f.save(fpath)
            foto_url = f"/uploads/{fname}"

        try:
            with SessionLocal() as s:
                rep_id = create_reporte(
                    s,
                    id_bano=id_bano,
                    categoria=categoria,
                    comentario=comentario or None,
                    foto_url=foto_url,
                    origen="qr",
                    creado_por_ip=request.remote_addr,
                )
            return jsonify({"ok": True, "reporte_id": rep_id})
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Error al guardar"}), 500

    @app.route("/uploads/<path:fname>")
    def uploads(fname):
        return send_from_directory(app.config["UPLOAD_FOLDER"], fname)

    # ---------- API: catálogo de baños ----------
    @app.route("/api/banos")
    def api_banos():
        with SessionLocal() as s:
            return jsonify(get_banos(s, solo_activos=True))

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

        with SessionLocal() as s:
            data = list_reportes(
                s,
                desde=desde,
                hasta=hasta,
                zona=zona,
                id_bano=id_b,
                search=search,
                page=page,
                per_page=per_page,
            )

        # añade creado_local a cada item
        items2 = []
        for it in data["items"]:
            try:
                raw = it.get("creado_en")
                if isinstance(raw, str):
                    # ISO con Z o con offset
                    dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                else:
                    dt = raw
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                it["creado_local"] = dt.astimezone(tzinfo).isoformat()
            except Exception:
                it["creado_local"] = it.get("creado_en")
            items2.append(it)
        data["items"] = items2

        return jsonify(data)

    # ---------- API: KPIs ----------
    @app.route("/api/kpis")
    def kpis():
        desde = request.args.get("desde")
        hasta = request.args.get("hasta")
        zona  = request.args.get("zona")
        id_b  = request.args.get("id_bano")
        tzinfo = get_tz_from_request()

        with SessionLocal() as s:
            rows = fetch_rows_for_kpis(
                s, desde=desde, hasta=hasta, zona=zona, id_bano=id_b
            )
            banos_catalogo = {b["id"]: b for b in get_banos(s, solo_activos=True)}

        por_categoria, por_bano, por_dia, por_zona = {}, {}, {}, {}
        for categoria, creado_en, id_bano_r, zona_r in rows:
            por_categoria[categoria] = por_categoria.get(categoria, 0) + 1
            por_bano[id_bano_r] = por_bano.get(id_bano_r, 0) + 1
            por_zona[zona_r] = por_zona.get(zona_r, 0) + 1

            try:
                dt = creado_en
                if isinstance(dt, str):
                    dt = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                dloc = dt.astimezone(tzinfo).date().isoformat()
            except Exception:
                dloc = str(creado_en)[:10]
            por_dia[dloc] = por_dia.get(dloc, 0) + 1

        top_banos = sorted(
            [
                {
                    "id_bano": k,
                    "nombre": banos_catalogo.get(k, {}).get("nombre", k),
                    "total": v,
                }
                for k, v in por_bano.items()
            ],
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

        total = sum(por_categoria.values())
        return jsonify(
            {
                "total_reportes": total,
                "por_categoria": por_categoria,
                "por_bano": por_bano,
                "por_dia": por_dia,
                "por_zona": por_zona,
                "top_banos": top_banos,
                "banos_catalogo": banos_catalogo,
            }
        )

    # --- Encuesta/kiosco sin QR ---
    @app.route("/encuesta")
    def encuesta_page():
        return render_template("encuesta.html")

    # ---------- Reportes (sirve el HTML estático) ----------
    @app.route("/reportes")
    def reportes_page():
        return app.send_static_file("reportes/reportes.html")

    @app.route("/api/health")
    def health():
        try:
            with SessionLocal() as s:
                _ = get_banos(s, solo_activos=False)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "err": str(e)}, 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
