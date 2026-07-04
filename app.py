import os
import re
import json
import threading
import unicodedata
import urllib.parse
from functools import wraps

import requests as _http
from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, abort, session, Response
)
from db import get_db, init_db, now_str, IS_PG
from scraper import scrape

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-cambiar-en-produccion")

# Crea las tablas al arrancar (sirve también cuando lo levanta gunicorn en el host)
init_db()

ADVISOR_NAME = "Elianne"
ADVISOR_WHATSAPP = "59892364337"  # +598 92 364 337

# Contraseña del panel del corredor. En el host se configura con la variable ADMIN_PASSWORD.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "etxe2026")

# Notificación al corredor por WhatsApp (vía CallMeBot, gratis).
# NOTIFY_WHATSAPP: número del corredor (sin '+', con código país). Default: el del asesor.
# CALLMEBOT_APIKEY: la apikey que te da el bot por WhatsApp tras hacer el opt-in.
NOTIFY_WHATSAPP = os.environ.get("NOTIFY_WHATSAPP", "").strip() or ADVISOR_WHATSAPP
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "").strip()


def _notify_admin_whatsapp(message):
    """Envía un WhatsApp al corredor vía CallMeBot. Fire-and-forget (no bloquea la respuesta).
    Silencioso si no está configurada la apikey."""
    if not CALLMEBOT_APIKEY or not NOTIFY_WHATSAPP:
        return False
    def _send():
        try:
            url = (
                "https://api.callmebot.com/whatsapp.php?"
                f"phone={NOTIFY_WHATSAPP}"
                f"&text={urllib.parse.quote(message)}"
                f"&apikey={CALLMEBOT_APIKEY}"
            )
            _http.get(url, timeout=15)
        except Exception:
            pass  # No queremos que un fallo de notif corte el flujo del usuario.
    threading.Thread(target=_send, daemon=True).start()
    return True


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form.get("password") or "") == ADMIN_PASSWORD:
            session["admin"] = True
            session.permanent = True
            dest = request.args.get("next") or url_for("admin_home")
            return redirect(dest)
        error = "Contraseña incorrecta."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


_MAPS_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def coords_from_maps(url):
    """Extrae (lat, lng) de un link de Google Maps. Expande short links (maps.app.goo.gl).
    Devuelve (None, None) si no encuentra coordenadas."""
    if not url or not url.strip():
        return (None, None)
    u = url.strip()
    # Expandir short links siguiendo el redirect
    if re.search(r"(maps\.app\.goo\.gl|goo\.gl/maps|g\.co/kgs)", u):
        try:
            r = _http.get(u, headers={"User-Agent": _MAPS_BROWSER_UA}, timeout=12, allow_redirects=True)
            u = r.url
        except Exception:
            pass
    # !3d<lat>!4d<lng> es la coordenada exacta del lugar (la más precisa)
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", u)
    if not m:
        m = re.search(r"[?&](?:q|ll|daddr|destination|center)=(-?\d+\.\d+),\s*(-?\d+\.\d+)", u)
    if not m:
        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", u)  # centro del mapa (aprox)
    if m:
        return (m.group(1), m.group(2))
    return (None, None)


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "cliente"


def unique_slug(conn, base):
    slug = base
    i = 2
    while conn.execute("SELECT 1 FROM clients WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{i}"
        i += 1
    return slug


# ---------- Admin ----------

@app.route("/")
@login_required
def admin_home():
    conn = get_db()
    clients = conn.execute(
        """
        SELECT c.*,
               COUNT(p.id) AS total,
               SUM(CASE WHEN p.status = 'interesa' THEN 1 ELSE 0 END) AS interesa,
               SUM(CASE WHEN p.status != 'pendiente' THEN 1 ELSE 0 END) AS respondidas
        FROM clients c
        LEFT JOIN properties p ON p.client_id = c.id
        GROUP BY c.id
        ORDER BY c.created_at DESC
        """
    ).fetchall()
    conn.close()
    return render_template("admin.html", clients=clients)


@app.route("/clientes", methods=["POST"])
@login_required
def create_client():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("admin_home"))
    conn = get_db()
    slug = unique_slug(conn, slugify(name))
    cid = conn.insert_id(
        "INSERT INTO clients (name, slug, created_at) VALUES (?, ?, ?)",
        (name, slug, now_str()),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("client_detail", client_id=cid))


@app.route("/health")
def health():
    """Endpoint del 'despertador'. Toca la DB para mantener viva a Neon también,
    y devuelve 503 si la base no responde (así te enterás si algo está mal)."""
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return "ok", 200
    except Exception as e:
        return f"db-error: {e}", 503


@app.route("/admin/cliente/<int:client_id>")
@login_required
def client_detail(client_id):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        abort(404)
    props = conn.execute(
        "SELECT * FROM properties WHERE client_id = ? ORDER BY position, id", (client_id,)
    ).fetchall()
    conn.close()
    stats = {
        "total": len(props),
        "interesa": sum(1 for p in props if p["status"] == "interesa"),
        "no_interesa": sum(1 for p in props if p["status"] == "no_interesa"),
        "pendiente": sum(1 for p in props if p["status"] == "pendiente"),
        "visitadas": sum(1 for p in props if p["visited_at"]),
    }
    return render_template("client_detail.html", client=client, props=props, stats=stats)


@app.route("/admin/cliente/<int:client_id>/propiedades", methods=["POST"])
@login_required
def add_property(client_id):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        abort(404)
    urls_raw = request.form.get("urls") or ""
    urls = [u.strip() for u in re.split(r"[\s\n]+", urls_raw) if u.strip().startswith("http")]
    maxpos = conn.execute(
        "SELECT COALESCE(MAX(position), 0) AS m FROM properties WHERE client_id = ?", (client_id,)
    ).fetchone()["m"]
    pos = maxpos
    for u in urls:
        pos += 1
        # Scrape con guardado inmediato por cada URL: si el scraping de alguna tarda,
        # las anteriores quedan guardadas (no se pierden por timeout de gunicorn).
        try:
            data = scrape(u)
        except Exception as e:
            print(f"[add_property] scrape {u} fallo: {e}")
            data = {"title": None, "price": None, "image": None, "bedrooms": None,
                    "area": None, "location": None, "description": None, "expenses": None}
        try:
            conn.execute(
                """INSERT INTO properties
                   (client_id, url, title, price, image, bedrooms, area, location, description, expenses, position, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (client_id, u, data.get("title"), data.get("price"), data.get("image"), data.get("bedrooms"),
                 data.get("area"), data.get("location"), data.get("description"), data.get("expenses"), pos, now_str()),
            )
            conn.commit()  # commit por URL para que las guardadas persistan
        except Exception as e:
            print(f"[add_property] insert {u} fallo: {e}")
    conn.close()
    return redirect(url_for("client_detail", client_id=client_id))


@app.route("/admin/propiedad/<int:prop_id>/editar", methods=["POST"])
@login_required
def edit_property(prop_id):
    conn = get_db()
    p = conn.execute("SELECT client_id FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        conn.close()
        abort(404)
    map_url = (request.form.get("map_url") or "").strip()
    lat, lng = coords_from_maps(map_url) if map_url else (None, None)
    conn.execute(
        """UPDATE properties SET title=?, price=?, image=?, bedrooms=?, area=?, location=?, description=?, expenses=?,
               map_url=?, lat=?, lng=?
           WHERE id=?""",
        (request.form.get("title"), request.form.get("price"), request.form.get("image"),
         request.form.get("bedrooms"), request.form.get("area"), request.form.get("location"),
         request.form.get("description"), request.form.get("expenses"),
         map_url or None, lat, lng, prop_id),
    )
    conn.commit()
    cid = p["client_id"]
    conn.close()
    return redirect(url_for("client_detail", client_id=cid))


@app.route("/admin/propiedad/<int:prop_id>/eliminar", methods=["POST"])
@login_required
def delete_property(prop_id):
    conn = get_db()
    p = conn.execute("SELECT client_id FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        conn.close()
        abort(404)
    conn.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
    conn.commit()
    cid = p["client_id"]
    conn.close()
    return redirect(url_for("client_detail", client_id=cid))


def _refresh_property(conn, prop_id):
    """Re-extrae el aviso. Rellena los campos vacíos y, además, reemplaza
    título/descripción si están largos (auto-extraídos sin recortar)."""
    p = conn.execute("SELECT * FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        return None
    data = scrape(p["url"])
    fields = ("title", "price", "image", "bedrooms", "area", "location", "description", "expenses")
    updates = {f: data.get(f) for f in fields if not (p[f] or "").strip() and data.get(f)}
    # Reemplaza títulos/descripciones largos por la versión recortada nueva (más comercial).
    if data.get("title") and len(p["title"] or "") > 80 and data["title"] != (p["title"] or ""):
        updates["title"] = data["title"]
    if data.get("description") and len(p["description"] or "") > 200 and data["description"] != (p["description"] or ""):
        updates["description"] = data["description"]
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE properties SET {sets} WHERE id=?", (*updates.values(), prop_id))
    return p["client_id"]


@app.route("/admin/propiedad/<int:prop_id>/actualizar", methods=["POST"])
@login_required
def refresh_property(prop_id):
    conn = get_db()
    cid = _refresh_property(conn, prop_id)
    conn.commit()
    conn.close()
    if cid is None:
        abort(404)
    return redirect(url_for("client_detail", client_id=cid))


@app.route("/admin/cliente/<int:client_id>/actualizar", methods=["POST"])
@login_required
def refresh_client(client_id):
    conn = get_db()
    rows = conn.execute("SELECT id FROM properties WHERE client_id = ?", (client_id,)).fetchall()
    for r in rows:
        try:
            _refresh_property(conn, r["id"])
        except Exception as e:
            print(f"[refresh] prop {r['id']} fallo: {e}")  # sigue con las demas
    conn.commit()
    conn.close()
    return redirect(url_for("client_detail", client_id=client_id))


@app.route("/admin/propiedad/<int:prop_id>/visita", methods=["POST"])
@login_required
def visit_property(prop_id):
    """Marca una propiedad como visitada y guarda un comentario interno (no se muestra al cliente)."""
    conn = get_db()
    p = conn.execute("SELECT client_id, visited_at FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        conn.close()
        abort(404)
    is_visited = request.form.get("visited") == "1"
    visit_comment = request.form.get("visit_comment") or ""
    # Si recién la marcan como visitada, registro la fecha; si ya tenía, la mantengo.
    if is_visited:
        visited_at = p["visited_at"] or now_str()
    else:
        visited_at = None
    conn.execute(
        "UPDATE properties SET visited_at=?, visit_comment=? WHERE id=?",
        (visited_at, visit_comment, prop_id),
    )
    conn.commit()
    cid = p["client_id"]
    conn.close()
    return redirect(url_for("client_detail", client_id=cid) + f"#prop-{prop_id}")


@app.route("/admin/cliente/<int:client_id>/eliminar", methods=["POST"])
@login_required
def delete_client(client_id):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_home"))


# ---------- Portal cliente (público) ----------

@app.route("/p/<slug>")
def portal(slug):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE slug = ?", (slug,)).fetchone()
    if not client:
        conn.close()
        abort(404)
    props = conn.execute(
        "SELECT * FROM properties WHERE client_id = ? ORDER BY position, id", (client["id"],)
    ).fetchall()
    conn.close()
    props_json = json.dumps([
        {"id": p["id"], "url": p["url"], "title": p["title"], "price": p["price"],
         "image": p["image"], "bedrooms": p["bedrooms"], "area": p["area"],
         "location": p["location"], "description": p["description"], "expenses": p["expenses"],
         "lat": p["lat"], "lng": p["lng"],
         "status": p["status"], "comment": p["comment"] or ""}
        for p in props
    ])
    return render_template("portal.html", client=client, props=props, props_json=props_json,
                           advisor_name=ADVISOR_NAME, advisor_wpp=ADVISOR_WHATSAPP)


@app.route("/api/cliente/<slug>/finalizar", methods=["POST"])
def finalize_selection(slug):
    """El portal del cliente marca su selección como terminada (notifica al corredor)."""
    conn = get_db()
    c = conn.execute("SELECT id, name FROM clients WHERE slug = ?", (slug,)).fetchone()
    if not c:
        conn.close()
        return jsonify({"ok": False}), 404
    conn.execute("UPDATE clients SET finished_at = ? WHERE id = ?", (now_str(), c["id"]))
    counts = conn.execute(
        """SELECT
              COUNT(*) AS t,
              SUM(CASE WHEN status='interesa'    THEN 1 ELSE 0 END) AS i,
              SUM(CASE WHEN status='no_interesa' THEN 1 ELSE 0 END) AS n
           FROM properties WHERE client_id = ?""",
        (c["id"],),
    ).fetchone()
    conn.commit()
    cid, cname = c["id"], c["name"]
    conn.close()

    msg = (
        f"🏠 {cname} terminó su selección.\n"
        f"🟢 Le interesa: {counts['i'] or 0}   ⚪ Descarta: {counts['n'] or 0}   (de {counts['t'] or 0})\n"
        f"Ver: {request.host_url}admin/cliente/{cid}"
    )
    _notify_admin_whatsapp(msg)
    return jsonify({"ok": True})


@app.route("/admin/backup")
@login_required
def backup():
    """Descarga un JSON con todos los datos para guardar como copia de seguridad."""
    conn = get_db()
    clients = [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id").fetchall()]
    properties = [dict(r) for r in conn.execute("SELECT * FROM properties ORDER BY id").fetchall()]
    conn.close()
    payload = {
        "version": 1,
        "generated_at": now_str(),
        "clients": clients,
        "properties": properties,
        "counts": {"clients": len(clients), "properties": len(properties)},
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    stamp = now_str().replace(" ", "_").replace(":", "-")
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="inmocrm-backup-{stamp}.json"'},
    )


@app.route("/admin/estado")
@login_required
def system_status():
    """Página de salud del sistema: DB, integraciones, contadores."""
    info = {
        "db_ok": False, "db_type": "Postgres (Neon)" if IS_PG else "SQLite local",
        "clients": 0, "properties": 0, "finished": 0, "visited": 0,
        "callmebot_ok": bool(CALLMEBOT_APIKEY),
        "notify_to": NOTIFY_WHATSAPP,
        "secret_key_custom": os.environ.get("SECRET_KEY") not in (None, "", "dev-secret-cambiar-en-produccion"),
        "admin_password_custom": ADMIN_PASSWORD != "etxe2026",
        "advisor_name": ADVISOR_NAME,
        "advisor_wpp": ADVISOR_WHATSAPP,
    }
    try:
        conn = get_db()
        info["db_ok"] = True
        info["clients"] = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"]
        info["properties"] = conn.execute("SELECT COUNT(*) AS n FROM properties").fetchone()["n"]
        info["finished"] = conn.execute("SELECT COUNT(*) AS n FROM clients WHERE finished_at IS NOT NULL").fetchone()["n"]
        info["visited"] = conn.execute("SELECT COUNT(*) AS n FROM properties WHERE visited_at IS NOT NULL").fetchone()["n"]
        conn.close()
    except Exception as e:
        info["db_error"] = str(e)
    return render_template("status.html", info=info)


@app.route("/admin/notif-test", methods=["POST"])
@login_required
def notif_test():
    """Manda un WhatsApp de prueba al corredor para validar el setup de CallMeBot."""
    ok = _notify_admin_whatsapp("✅ Test de notificación de inmocrm — está todo conectado.")
    return jsonify({"ok": ok, "configurado": bool(CALLMEBOT_APIKEY)})


@app.route("/api/propiedad/<int:prop_id>/responder", methods=["POST"])
def respond(prop_id):
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status")
    comment = data.get("comment", "")
    if status not in ("interesa", "no_interesa", "pendiente"):
        return jsonify({"ok": False, "error": "estado inválido"}), 400
    conn = get_db()
    p = conn.execute("SELECT 1 FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        conn.close()
        return jsonify({"ok": False}), 404
    conn.execute(
        "UPDATE properties SET status=?, comment=?, responded_at=? WHERE id=?",
        (status, comment, now_str(), prop_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
