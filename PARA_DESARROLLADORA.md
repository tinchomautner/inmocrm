# Guía para desarrolladora — Inmocrm

Bienvenida 👋 Este documento tiene TODO lo que necesitás para entender, correr y modificar
este proyecto. Está pensado para leerse una vez de arriba a abajo. Si usás Codex u otro
asistente, dejá que lea este archivo primero: le da el contexto completo.

---

## 1. Qué es esto

Un mini-CRM inmobiliario. El corredor (una asesora llamada Elianne) crea clientes, les carga
links de propiedades (Mercado Libre, InfoCasas, etc.), y a cada cliente le sale un **link
único** que le manda por WhatsApp. El cliente entra, marca **Me interesa / No me interesa** en
cada propiedad y deja comentarios. El corredor ve todo en un panel.

- **Panel del corredor** (privado, con login): `/` y `/admin/...`
- **Portal del cliente** (público, sin login): `/p/<slug>`

Está en producción en **Render**: https://inmocrm.onrender.com

---

## 2. Stack (a propósito simple)

- **Python 3 + Flask** — el servidor web. Sin framework de frontend: HTML server-rendered
  con plantillas Jinja2 + un poco de JavaScript vanilla en cada página.
- **Base de datos**: SQLite en local (un archivo `inmocrm.db`) y **Postgres (Neon)** en
  producción. El mismo código sirve para las dos (ver `db.py`).
- **Scraping**: `requests` + `BeautifulSoup` (no hay navegador headless).
- **Mapa**: Leaflet + OpenStreetMap (gratis, sin API key).
- **Deploy**: push a GitHub → Render redeploya solo.

No hay build step, ni npm, ni bundler. Es a propósito: para poder tocar y ver el cambio rápido.

---

## 3. Correrlo en tu compu (local)

```bash
git clone https://github.com/tinchomautner/inmocrm.git
cd inmocrm
pip install -r requirements.txt
python app.py
```

Abrí http://localhost:5000. La primera vez se crea solo el archivo `inmocrm.db` (SQLite) con
las tablas vacías. Login del panel: la contraseña por defecto en local es **`etxe2026`**
(en producción es otra, ver variables de entorno abajo).

> En local NO se usa la base de producción (Neon). Trabajás con una base SQLite tuya, aislada.
> Podés romper y borrar tranquila sin afectar los datos reales.

---

## 4. Mapa del proyecto (qué hace cada archivo)

```
app.py                  # TODAS las rutas Flask + lógica. Es el corazón. Empezá por acá.
db.py                   # Conexión y esquema. Soporta SQLite (local) y Postgres (prod).
scraper.py              # Extrae datos de los links de propiedades.
requirements.txt        # Dependencias Python.
render.yaml / Procfile  # Config de deploy (Render).
templates/
  admin.html            # Panel: listado de clientes.
  client_detail.html    # Panel: un cliente + sus propiedades (editar, actualizar, visitas).
  portal.html           # Lo que ve el CLIENTE (fichas, tabs, mapa, finalizar).
  login.html            # Login del panel.
  status.html           # Página de estado del sistema (/admin/estado).
static/
  style.css             # TODOS los estilos. Un solo archivo.
  img/                  # Logos de Etxe.
```

### Flujo de una request típica
1. El navegador pide una URL → Flask matchea una `@app.route` en `app.py`.
2. La función lee/escribe en la base con `get_db()` y renderiza una plantilla de `templates/`.
3. El portal del cliente (`portal.html`) recibe las propiedades como JSON (`props_json`) y
   arma las fichas con JavaScript.

---

## 5. La base de datos

Dos tablas, definidas en `db.py` → `init_db()`:

- **clients**: `id, name, slug, finished_at, created_at`
- **properties**: `id, client_id, url, title, price, image, bedrooms, area, location, address,
  description, expenses, position, status, comment, responded_at, visited_at, visit_comment,
  map_url, lat, lng, created_at`

`status` de una propiedad es uno de: `pendiente` (nueva, sin responder), `interesa`, `no_interesa`.

### ⚠️ Cómo agregar una columna nueva (importante)
La base de producción YA existe con datos. Para agregar un campo sin romper nada, hay un helper
`_ensure_column()` que agrega la columna si falta. Patrón a seguir en `db.py` dentro de `init_db()`:

```python
_ensure_column(conn, "properties", "mi_campo_nuevo", "TEXT")
```

Y agregá también la columna en el `CREATE TABLE` (para bases nuevas). Con eso, al deployar,
la columna se crea sola tanto en SQLite como en Postgres. **Nunca borres columnas ni datos.**

---

## 6. El scraper (cómo agregar una inmobiliaria nueva)

`scraper.py` → función `scrape(url)`. Estrategia, en orden:

1. **Sitios con handler propio** (webs 100% JavaScript que no traen datos en el HTML). Hoy hay
   uno: `inmobiliariagolf.com.uy`, que usa el backend **Tokko** y tiene una API interna
   (`_scrape_golf`). Se despacha por dominio al principio de `scrape()`.
2. **Lector genérico** (`_parse`): saca datos de Open Graph (`og:title`, `og:image`, ...),
   JSON-LD (`<script type="application/ld+json">`) y, si falta, de regex sobre el texto.
   Esto cubre la mayoría de las inmobiliarias.
3. **Reintento con "User-Agent social"**: Mercado Libre le muestra a los bots una página
   anti-robot. Si falta precio/imagen o el título es basura, se reintenta con el UA de
   Facebook/WhatsApp, que sí trae la página completa.

### Para agregar un sitio JS nuevo (tipo Tokko)
1. Abrí el aviso en el navegador con las DevTools → pestaña **Network** → recargá y buscá la
   llamada que trae los datos (suele ser un `.php`/`.json` con el `id` de la propiedad).
2. Replicá esa llamada con `requests` (mirá `_scrape_golf` como ejemplo: hace un POST con el id).
3. Parseá el JSON al dict que devuelve `scrape()` (mismas keys: `title, price, image, bedrooms,
   area, location, address, description, expenses, lat, lng`).
4. Agregá el dominio al dispatcher al principio de `scrape()`.

> Nota: muchas inmobiliarias de UY/AR usan Tokko. El endpoint varía por sitio, por eso hoy hay
> un handler por dominio. Si aparecen varias Tokko, se puede generalizar la detección.

El scraper **nunca lanza excepción**: si un sitio no se puede leer, devuelve el dict con campos
en `None` y la propiedad se completa a mano desde "Editar datos" en el panel.

---

## 7. Variables de entorno (producción)

Se configuran en **Render → el servicio → Environment**. En local no hacen falta (hay defaults).

| Variable | Para qué | Si falta |
|----------|----------|----------|
| `DATABASE_URL` | Conexión Postgres (Neon). Hace que los datos persistan. | Usa SQLite local. |
| `ADMIN_PASSWORD` | Contraseña del panel. | Queda `etxe2026` (insegura, es pública). |
| `SECRET_KEY` | Firma las sesiones de login. | Usa un default (inseguro). |
| `NOTIFY_WHATSAPP` | Número que recibe aviso cuando un cliente finaliza. | Usa el de la asesora. |
| `CALLMEBOT_APIKEY` | Habilita el WhatsApp automático (servicio CallMeBot). | No manda WhatsApp (pero el badge en el panel sí avisa). |

Podés ver el estado de todo esto en vivo entrando a **`/admin/estado`**.

---

## 8. Deploy (cómo publicar un cambio)

1. Editás, probás en local (`python app.py`).
2. Subís a GitHub:
   ```bash
   git add -A
   git commit -m "descripción del cambio"
   git push
   ```
3. **Render redeploya solo** en 1-2 minutos. Mirás el progreso en Render → Events.

No hay que hacer nada más. La base (Neon) no se toca en el deploy: los datos quedan.

> Antes de un cambio grande, entrá a `/admin/estado` → **Descargar backup** para tener una
> copia de los datos por las dudas.

---

## 9. Cosas que conviene saber (aprendidas a los golpes)

- **El scraping de Mercado Libre** funciona con el truco del User-Agent social. Si algún día
  deja de andar, es probable que ML haya cambiado su anti-bot; revisar `SOCIAL_UA` en `scraper.py`.
- **etxe.com.uy** carga el precio por JavaScript: no se puede sacar el precio, se pone a mano.
- **Render free** duerme la app tras 15 min sin uso. Un cron externo (cron-job.org) pinguea
  `/health` cada 10 min para mantenerla despierta. Si la app tarda ~50s en abrir, revisar el cron.
- **La imagen de las fichas** usa `object-fit: cover` con `overflow:hidden` para no mostrar
  bordes negros. Si tocás el layout de la galería (`.gal` en style.css), cuidá eso.
- **Tabs del portal**: las propiedades se agrupan en Nuevas / Me interesan / Descartadas según
  su `status`. La lógica está en `portal.html` (`renderTab`, `switchTab`, `goToProperty`).

---

## 10. Contacto

Repo: https://github.com/tinchomautner/inmocrm
App en vivo: https://inmocrm.onrender.com

Cualquier duda de "por qué está hecho así", buscá el commit relacionado con `git log` — los
mensajes de commit cuentan la historia de cada feature.
