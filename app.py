import os
import re
import json
import unicodedata
from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, abort
)
from db import get_db, init_db
from scraper import scrape

app = Flask(__name__)

# Crea las tablas al arrancar (sirve también cuando lo levanta gunicorn en el host)
init_db()

ADVISOR_NAME = "Elianne"
ADVISOR_WHATSAPP = "59892364337"  # +598 92 364 337


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
def create_client():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("admin_home"))
    conn = get_db()
    slug = unique_slug(conn, slugify(name))
    cur = conn.execute("INSERT INTO clients (name, slug) VALUES (?, ?)", (name, slug))
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return redirect(url_for("client_detail", client_id=cid))


@app.route("/admin/cliente/<int:client_id>")
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
    }
    return render_template("client_detail.html", client=client, props=props, stats=stats)


@app.route("/admin/cliente/<int:client_id>/propiedades", methods=["POST"])
def add_property(client_id):
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        abort(404)
    urls_raw = request.form.get("urls") or ""
    urls = [u.strip() for u in re.split(r"[\s\n]+", urls_raw) if u.strip().startswith("http")]
    maxpos = conn.execute(
        "SELECT COALESCE(MAX(position), 0) FROM properties WHERE client_id = ?", (client_id,)
    ).fetchone()[0]
    pos = maxpos
    for u in urls:
        pos += 1
        data = scrape(u)
        conn.execute(
            """INSERT INTO properties
               (client_id, url, title, price, image, bedrooms, area, location, description, position)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (client_id, u, data["title"], data["price"], data["image"], data["bedrooms"],
             data["area"], data["location"], data["description"], pos),
        )
    conn.commit()
    conn.close()
    return redirect(url_for("client_detail", client_id=client_id))


@app.route("/admin/propiedad/<int:prop_id>/editar", methods=["POST"])
def edit_property(prop_id):
    conn = get_db()
    p = conn.execute("SELECT client_id FROM properties WHERE id = ?", (prop_id,)).fetchone()
    if not p:
        conn.close()
        abort(404)
    conn.execute(
        """UPDATE properties SET title=?, price=?, image=?, bedrooms=?, area=?, location=?, description=?
           WHERE id=?""",
        (request.form.get("title"), request.form.get("price"), request.form.get("image"),
         request.form.get("bedrooms"), request.form.get("area"), request.form.get("location"),
         request.form.get("description"), prop_id),
    )
    conn.commit()
    cid = p["client_id"]
    conn.close()
    return redirect(url_for("client_detail", client_id=cid))


@app.route("/admin/propiedad/<int:prop_id>/eliminar", methods=["POST"])
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


@app.route("/admin/cliente/<int:client_id>/eliminar", methods=["POST"])
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
         "location": p["location"], "description": p["description"],
         "status": p["status"], "comment": p["comment"] or ""}
        for p in props
    ])
    return render_template("portal.html", client=client, props=props, props_json=props_json,
                           advisor_name=ADVISOR_NAME, advisor_wpp=ADVISOR_WHATSAPP)


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
        "UPDATE properties SET status=?, comment=?, responded_at=datetime('now','localtime') WHERE id=?",
        (status, comment, prop_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
